// Included inside main.cpp's anonymous namespace after its ImGui/Win32 helpers.
using Json = nlohmann::json;
std::filesystem::path projectRoot() {
    std::filesystem::path p(loader::executableDirectory());
    for (int i = 0; i < 5; ++i, p = p.parent_path())
        if (std::filesystem::is_regular_file(p / "backend.py")) return p;
    throw std::runtime_error("Application backend is missing. Run it from the project folder.");
}
std::wstring quoteArg(const std::wstring& arg) {
    std::wstring result = L"\""; unsigned slashes{};
    for (wchar_t c : arg) {
        if (c == L'\\') { ++slashes; continue; }
        if (c == L'\"') { result.append(slashes * 2 + 1, L'\\'); result += c; }
        else { result.append(slashes, L'\\'); result += c; }
        slashes = 0;
    }
    result.append(slashes * 2, L'\\'); result += L'\"'; return result;
}
struct JobResult { bool ok{}; std::string message; Json settings; std::string hint; bool repairD3D9{}; };
JobResult runJob(const std::filesystem::path& root, const std::string& action,
    const std::string& game, const std::string& api, const Json& appearance) {
    try {
        auto folder = root / "jobs"; std::filesystem::create_directories(folder);
        const auto id = std::to_string(GetCurrentProcessId()) + "-" + std::to_string(GetTickCount64());
        const auto request = folder / (id + ".json");
        const auto response = folder / (id + "-result.json");
        Json job{{"action", action}, {"game", game}, {"api", api}, {"result", loader::utf8(response.wstring())}};
        if (action == "install" || action == "apply-settings" || action == "repair-d3d9") job["settings"] = appearance;
        { std::ofstream file(request); if (!file) throw std::runtime_error("Could not write operation request."); file << job.dump(2); }
        const auto python = loader::wide(DLSS_PYTHON_EXECUTABLE);
        std::wstring command = quoteArg(python) + L" " + quoteArg((root / "backend.py").wstring()) + L" " + quoteArg(request.wstring());
        STARTUPINFOW startup{}; startup.cb = sizeof(startup); startup.dwFlags = STARTF_USESHOWWINDOW; startup.wShowWindow = SW_HIDE;
        PROCESS_INFORMATION process{};
        if (!CreateProcessW(python.c_str(), command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
            nullptr, root.c_str(), &startup, &process))
            return {false, "Could not start the setup backend (Windows " + std::to_string(GetLastError()) + ")."};
        CloseHandle(process.hThread);
        const DWORD wait = WaitForSingleObject(process.hProcess, 180000);
        if (wait != WAIT_OBJECT_0) {
            TerminateProcess(process.hProcess, 1); WaitForSingleObject(process.hProcess, 5000); CloseHandle(process.hProcess);
            return {false, "Operation timed out. Close the game, then Restore if an installation was interrupted."};
        }
        CloseHandle(process.hProcess);
        std::ifstream file(response);
        if (!file) return {false, "Setup backend exited without a result. See the request in the jobs folder."};
        Json result; file >> result;
        return {result.value("ok", false), result.value("message", std::string("No operation result.")), result.value("settings", Json()),
            result.value("hint", std::string()), result.value("repair_d3d9", false)};
    } catch (const std::exception& e) { return {false, e.what()}; }
}
struct App {
    std::filesystem::path root;
    std::string game, status = "Select a game executable to begin.", currentAction;
    int api{};
    Json schema, appearance;
    int lookPreset{}, selectedTab{};
    bool customizationVisible{};
    bool appearanceDirty{};
    bool preserveStartupDraft{};
    bool lastOk = true, gameValid{}, gpuPassed{}, scrollLog{};
    bool repairD3D9{};
    std::future<JobResult> task;
    std::vector<std::string> messages;
    std::ofstream log;
    App() {
        root = projectRoot(); log.open(root / "setup.log", std::ios::app);
        { std::ifstream file(root / "customization.json"); file >> schema; }
        resetAppearance();
        try {
            std::ifstream settings(root / "settings.json");
            if (settings) {
                Json s; settings >> s; game = s.value("game", std::string()); api = std::clamp(s.value("api", 0), 0, 2);
                Json saved = s.value("appearance", appearance);
                for (const auto& field : schema["fields"]) {
                    const auto key = field["key"].get<std::string>();
                    if (!saved.contains(key)) continue;
                    if (field["type"] == "bool" && saved[key].is_boolean()) appearance[key] = saved[key];
                    else if (field["type"] != "bool" && saved[key].is_number()) {
                        const double value = saved[key].get<double>();
                        if (value >= field["min"].get<double>() && value <= field["max"].get<double>()) appearance[key] = saved[key];
                    }
                }
                lookPreset = std::clamp(s.value("lookPreset", 0), 0, static_cast<int>(schema["presets"].size()));
                appearanceDirty = s.value("appearanceDirty", false); preserveStartupDraft = appearanceDirty;
            }
        } catch (...) { }
        append("Universal DLSS 5 Loader ready. ReShade + Feeder + RenoDX + matching RTX 40 runtime are bundled.");
        if (!game.empty()) start("scan");
    }
    void append(const std::string& text) {
        SYSTEMTIME time{}; GetLocalTime(&time);
        char stamp[32]{}; snprintf(stamp, sizeof(stamp), "%02u:%02u:%02u  ", time.wHour, time.wMinute, time.wSecond);
        messages.emplace_back(std::string(stamp) + text); scrollLog = true;
        if (log) { log << messages.back() << '\n'; log.flush(); }
    }
    void start(const std::string& action) {
        if (task.valid()) return;
        currentAction = action; status = action == "gpu-test" ? "Running the real neural rendering test on your NVIDIA GPU..." : "Working...";
        const auto folder = root; const auto target = game; const auto controls = appearance;
        const std::string graphics = api == 2 ? "D3D9" : api == 1 ? "OpenGL" : "DirectX 11 / 12";
        persist();
        append(action == "gpu-test" ? "GPU Test started." : action + " started for " + game);
        task = std::async(std::launch::async, [folder, target, graphics, action, controls] { return runJob(folder, action, target, graphics, controls); });
    }
    void poll() {
        using namespace std::chrono_literals;
        if (task.valid() && task.wait_for(0ms) == std::future_status::ready) {
            auto result = task.get(); status = result.message; lastOk = result.ok;
            if (currentAction == "scan") {
                gameValid = result.ok; repairD3D9 = result.repairD3D9;
                if (result.ok && result.hint == "D3D9") api = 2;
                else if (result.ok && result.hint == "OpenGL") api = 1;
                persist();
            }
            if (result.ok && (currentAction == "repair-d3d9" || currentAction == "restore")) repairD3D9 = false;
            if (currentAction == "gpu-test") gpuPassed = result.ok;
            if (result.ok && result.settings.is_object() && !(currentAction == "scan" && preserveStartupDraft)) {
                appearance = result.settings; detectLookPreset(); appearanceDirty = false; persist();
            }
            if (result.ok && currentAction == "apply-settings") appearanceDirty = false;
            if (currentAction == "scan") preserveStartupDraft = false;
            append(result.message);
        }
    }
    void resetAppearance() {
        appearance = Json::object();
        for (const auto& field : schema["fields"]) appearance[field["key"].get<std::string>()] = field["default"];
        lookPreset = 0;
    }
    void persist() {
        try {
            std::ofstream settings(root / "settings.json");
            settings << Json{{"game", game}, {"api", api}, {"appearance", appearance}, {"lookPreset", lookPreset}, {"appearanceDirty", appearanceDirty}}.dump(2);
        } catch (...) { }
    }
    void detectLookPreset() {
        lookPreset = static_cast<int>(schema["presets"].size());
        for (size_t i = 0; i < schema["presets"].size(); ++i) {
            Json candidate = Json::object();
            for (const auto& field : schema["fields"]) candidate[field["key"].get<std::string>()] = field["default"];
            candidate.update(schema["presets"][i]["values"]);
            if (appearance == candidate) { lookPreset = static_cast<int>(i); break; }
        }
    }
    void changedAppearance() { appearanceDirty = true; lookPreset = static_cast<int>(schema["presets"].size()); persist(); }
    static void help(const std::string& text) {
        ImGui::SameLine(); ImGui::TextDisabled("(?)");
        if (ImGui::IsItemHovered()) { ImGui::BeginTooltip(); ImGui::PushTextWrapPos(ImGui::GetFontSize() * 32);
            ImGui::TextUnformatted(text.c_str()); ImGui::PopTextWrapPos(); ImGui::EndTooltip(); }
    }
    void appearanceField(const Json& field) {
        const auto key = field["key"].get<std::string>(); const auto label = field["label"].get<std::string>();
        const auto kind = field["type"].get<std::string>(); bool changed{};
        ImGui::PushID(key.c_str());
        if (kind == "bool") {
            bool value = appearance[key].get<bool>();
            if (ImGui::Checkbox(label.c_str(), &value)) { appearance[key] = value; changed = true; }
            help(field["help"].get<std::string>());
        } else {
            ImGui::TextUnformatted(label.c_str()); help(field["help"].get<std::string>()); ImGui::SetNextItemWidth(-1);
            if (field.contains("choices")) {
                int value = appearance[key].get<int>();
                const auto items = field["choices"].get<std::vector<std::string>>();
                if (ImGui::BeginCombo("##value", items[static_cast<size_t>(value)].c_str())) {
                    for (size_t i = 0; i < items.size(); ++i)
                        if (ImGui::Selectable(items[i].c_str(), value == static_cast<int>(i))) { appearance[key] = static_cast<int>(i); changed = true; }
                    ImGui::EndCombo();
                }
            } else if (kind == "int") {
                int value = appearance[key].get<int>();
                if (ImGui::SliderInt("##value", &value, field["min"].get<int>(), field["max"].get<int>(), "%d", ImGuiSliderFlags_AlwaysClamp)) { appearance[key] = value; changed = true; }
            } else {
                float value = appearance[key].get<float>();
                const bool percent = field.value("display", std::string()) == "percent";
                const float multiplier = percent ? 100.0f : 1.0f;
                value *= multiplier;
                if (ImGui::SliderFloat("##value", &value, field["min"].get<float>() * multiplier, field["max"].get<float>() * multiplier,
                    percent ? "%.0f%%" : "%.2f", ImGuiSliderFlags_AlwaysClamp)) { appearance[key] = value / multiplier; changed = true; }
            }
        }
        ImGui::PopID();
        if (changed) changedAppearance();
    }
    void drawCustomization(bool busy) {
        ImGui::BeginDisabled(busy);
        const auto& presets = schema["presets"];
        const int custom = static_cast<int>(presets.size());
        const auto name = lookPreset == custom ? std::string("Custom") : presets[lookPreset]["name"].get<std::string>();
        ImGui::SetNextItemWidth(260);
        if (ImGui::BeginCombo("Look preset", name.c_str())) {
            for (int i = 0; i < custom; ++i) {
                if (ImGui::Selectable(presets[i]["name"].get<std::string>().c_str(), lookPreset == i)) {
                    resetAppearance();
                    for (const auto& [key, value] : presets[i]["values"].items()) appearance[key] = value;
                    lookPreset = i; appearanceDirty = true; persist();
                }
            }
            ImGui::EndCombo();
        }
        ImGui::TextWrapped("%s", lookPreset == custom ? "Your own settings. Look presets are adjustable starting values for different scenes." : presets[lookPreset]["description"].get<std::string>().c_str());
        ImGui::Spacing();
        // Keep Apply and the status visible on laptop displays; the controls scroll.
        const float controlsHeight = std::max(150.0f, ImGui::GetContentRegionAvail().y - 180.0f);
        ImGui::BeginChild("appearance_controls", ImVec2(0, controlsHeight), ImGuiChildFlags_Borders);
        if (ImGui::BeginTable("appearance", 2, ImGuiTableFlags_SizingStretchSame | ImGuiTableFlags_BordersInnerV)) {
            for (const auto& group : {"Look", "Performance"}) {
                ImGui::TableNextColumn(); ImGui::TextColored(ImVec4(0.55f, 0.9f, 0.45f, 1), "%s", group); ImGui::Spacing();
                for (const auto& field : schema["fields"]) if (field["group"] == group) appearanceField(field);
            }
            ImGui::EndTable();
        }
        ImGui::EndChild();
        ImGui::Spacing(); ImGui::Separator(); ImGui::Spacing();
        if (ImGui::Button("Reset to balanced")) { resetAppearance(); appearanceDirty = true; persist(); }
        ImGui::SameLine();
        ImGui::BeginDisabled(!gameValid);
        if (ImGui::Button("Load game settings")) start("load-settings");
        ImGui::SameLine(); if (ImGui::Button("Apply to game")) start("apply-settings");
        ImGui::EndDisabled(); ImGui::EndDisabled();
        ImGui::TextWrapped("%s", appearanceDirty ? "Unsaved game changes. New installations use this look; use Apply to game for an existing install." : "New installations use this look. Apply to game saves it for the selected installed game.");
        ImGui::TextWrapped("Close the game before Apply. Changes take effect on next launch. Home opens live in-game controls.");
    }
    void draw(HWND window) {
        poll(); const bool busy = task.valid();
        const auto* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(vp->WorkPos); ImGui::SetNextWindowSize(vp->WorkSize);
        ImGui::Begin("Universal DLSS 5 Loader", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
            ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings);
        ImGui::TextColored(ImVec4(0.55f, 0.9f, 0.45f, 1), "Universal DLSS 5 Loader");
        ImGui::SameLine(); ImGui::TextDisabled("0.3.3 / NVIDIA RTX / ImGui");
        ImGui::Spacing();
        ImGui::TextWrapped("Install neural rendering into an offline game. The complete rendering bridge is included, with automatic backups and restore.");
        ImGui::Separator(); ImGui::Spacing();
        ImGui::Text("YOUR GAME");
        ImGui::BeginDisabled(busy);
        ImGui::SetNextItemWidth(-120);
        if (ImGui::InputTextWithHint("##game", "Choose the real game .exe, not its launcher", &game)) gameValid = false;
        ImGui::SameLine();
        if (ImGui::Button("Browse...", ImVec2(102, 0))) {
            const auto path = browse(window);
            if (!path.empty()) { game = loader::utf8(path); gameValid = false; start("scan"); }
        }
        ImGui::SetNextItemWidth(210); ImGui::Combo("Graphics API", &api, "DirectX 11 / 12\0OpenGL\0DirectX 9 (bridge)\0");
        ImGui::SameLine(); if (ImGui::Button("Inspect game")) start("scan");
        ImGui::TextDisabled("64-bit and 32-bit. Select the API used in the game's graphics settings.");
        ImGui::EndDisabled();
        ImGui::Spacing(); ImGui::Separator(); ImGui::Spacing();
        customizationVisible = false;
        if (ImGui::BeginTabBar("app_sections")) {
        if (ImGui::BeginTabItem("Setup", nullptr, selectedTab == 1 ? ImGuiTabItemFlags_SetSelected : 0)) {
        if (selectedTab == 1) selectedTab = 0;
        ImGui::Text("SETUP");
        ImGui::BeginDisabled(busy || !gameValid);
        if (ImGui::Button(repairD3D9 ? "Repair DirectX 9 setup" : "Install DLSS 5", ImVec2(repairD3D9 ? 240.f : 180.f, 38))) start(repairD3D9 ? "repair-d3d9" : "install");
        ImGui::SameLine(); if (ImGui::Button("Check installation", ImVec2(180, 38))) start("check");
        ImGui::SameLine(); if (ImGui::Button("Restore originals", ImVec2(180, 38))) start("restore");
        ImGui::EndDisabled();
        ImGui::Spacing();
        ImGui::BeginDisabled(busy);
        if (ImGui::Button("Test NVIDIA GPU", ImVec2(180, 34))) start("gpu-test");
        ImGui::SameLine();
        ImGui::BeginDisabled(!gameValid);
        if (ImGui::Button("Launch game", ImVec2(180, 34))) start("launch");
        ImGui::EndDisabled(); ImGui::SameLine();
        if (ImGui::Button("Open logs", ImVec2(180, 34))) {
            auto folder = root / "diagnostics/host64";
            if (!game.empty()) { try { folder = std::filesystem::path(loader::wide(game)).parent_path(); } catch (...) { } }
            ShellExecuteW(window, L"open", folder.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
        }
        ImGui::EndDisabled();
        ImGui::Spacing();
        ImGui::TextColored(gpuPassed ? ImVec4(0.55f, 0.9f, 0.45f, 1) : ImVec4(0.6f, 0.65f, 0.7f, 1),
            "%s", gpuPassed ? "GPU test: neural rendering verified" : "GPU test runs 300 evaluations and checks that the neural model actually ran.");
        ImGui::TextWrapped("After installing: launch on the NVIDIA GPU and press Home for the in-game controls. Close the game before installing or restoring. Shader/depth settings may need adjustment for your game.");
        ImGui::TextWrapped("Steam games launch through their detected Steam app. Legacy CS:GO always uses -insecure.");
        ImGui::TextWrapped("DirectX 9 includes the dgVoodoo DirectX 11 bridge. Vulkan requires another bridge.");
        ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Customize DLSS 5", nullptr, selectedTab == 2 ? ImGuiTabItemFlags_SetSelected : 0)) {
            customizationVisible = true;
            if (selectedTab == 2) selectedTab = 0;
            drawCustomization(busy); ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
        }
        ImGui::Spacing(); ImGui::Separator(); ImGui::Spacing();
        ImGui::TextColored(lastOk ? ImVec4(0.72f, 0.9f, 0.65f, 1) : ImVec4(1, 0.65f, 0.48f, 1), "%s", busy ? "WORKING" : lastOk ? "STATUS" : "NEEDS ATTENTION");
        ImGui::TextWrapped("%s", status.c_str());
        if (busy) { ImGui::TextDisabled("This window stays responsive while setup runs. GPU Test can take up to 90 seconds."); }
        if (!customizationVisible) {
        ImGui::Spacing(); ImGui::Text("ACTIVITY");
        ImGui::BeginChild("activity", ImVec2(0, 0), ImGuiChildFlags_Borders);
        for (const auto& line : messages) ImGui::TextWrapped("%s", line.c_str());
        if (scrollLog) { ImGui::SetScrollHereY(1); scrollLog = false; }
        ImGui::EndChild();
        }
        ImGui::End();
    }
};
