from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAssetTests(unittest.TestCase):
    def test_github_readme_banner_and_screenshots_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for relative in (
            "assets/readme-banner.jpg",
            "assets/screenshots/main-menu.png",
            "assets/screenshots/transcription-queue.png",
            "assets/screenshots/dictation.png",
            "assets/screenshots/ai-processing.png",
            "assets/screenshots/help.png",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertIn(relative, readme)

    def test_release_version_is_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        installer = (ROOT / "installer" / "Spiker.iss").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:\.\d+)?$")
        self.assertIn(f'#define AppVersion "{version}"', installer)
        self.assertIn("Spiker-Setup-<версия>.exe", readme)

    def test_build_installs_test_dependencies_including_pillow(self):
        test_requirements = (ROOT / "res" / "requirements-test.txt").read_text(encoding="utf-8")
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertRegex(test_requirements, r"(?im)^Pillow>=11,<13$")
        self.assertIn("requirements-test.txt", build)
        self.assertIn("requirements-test.txt", workflow)

    def test_build_recovers_partial_venv_when_ensurepip_fails(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        helper = (ROOT / "scripts" / "bootstrap_build_pip.py").read_text(encoding="utf-8")
        self.assertIn("--without-pip", build)
        self.assertIn("$PipBootstrapScript", build)
        self.assertIn("& $Python $PipBootstrapScript", build)
        self.assertIn("ensurepip", helper)
        self.assertIn("https://bootstrap.pypa.io/get-pip.py", helper)
        self.assertIn("The isolated build environment has no working pip after bootstrap", build)


    def test_build_fix_documentation_is_included(self):
        doc = ROOT / "docs" / "BUILD_FIX_3.1.0.md"
        self.assertTrue(doc.is_file())
        content = doc.read_text(encoding="utf-8")
        for required in ("NativeCommandError", "ensurepip", "get-pip.py", "--without-pip"):
            self.assertIn(required, content)

    def test_build_bootstraps_pip_before_any_pip_command(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        helper_path = ROOT / "scripts" / "bootstrap_build_pip.py"
        self.assertTrue(helper_path.is_file())
        helper = helper_path.read_text(encoding="utf-8")
        self.assertIn("$PipBootstrapScript", build)
        self.assertIn("& $Python $PipBootstrapScript", build)
        self.assertNotIn("& $Python -m pip --version", build)
        bootstrap_call = build.index("& $Python $PipBootstrapScript")
        first_install = build.index("& $Python -m pip install --upgrade pip")
        self.assertLess(bootstrap_call, first_install)
        self.assertIn("-m", helper)
        self.assertIn("ensurepip", helper)
        self.assertIn("https://bootstrap.pypa.io/get-pip.py", helper)
        self.assertIn('"-m", "pip", "--version"', helper)
        self.assertIn("capture_output=True", helper)

    def test_build_bundles_model_and_checks_hash(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        source = (ROOT / "models" / "whisper" / "MODEL_SOURCE.md").read_text(encoding="utf-8")
        self.assertIn("ggml-small.bin", build)
        self.assertIn("Get-Sha256Hex", build)
        self.assertIn("ggml-small.bin", spec)
        self.assertIn("SHA-256", source)

    def test_spec_does_not_bundle_arbitrary_local_models(self):
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        self.assertIn('whisper_default = ROOT / "models" / "whisper" / "ggml-small.bin"', spec)
        self.assertNotIn('for folder in ("icons", "models")', spec)

    def test_github_about_has_copy_ready_description(self):
        about = (ROOT / "GITHUB_ABOUT.md").read_text(encoding="utf-8")
        self.assertIn("Description field", about)
        self.assertIn("Suggested topics", about)
        self.assertIn("assets/readme-banner.jpg", about)

    def test_build_waits_for_smoke_process_and_retries_zip(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("Start-Process -FilePath $Exe -ArgumentList $SmokeArgs -PassThru", build)
        self.assertIn("WaitForExit", build)
        self.assertIn("Portable ZIP creation failed", build)
        self.assertIn("$ArchiveAttempt -le 5", build)
        self.assertIn(".smoke-user-data\\logs\\application.log", build)

    def test_3_1_0_docs_cover_new_offline_features(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        release = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ARCHITECTURE_AND_ROADMAP_3.1.0.md").read_text(encoding="utf-8")
        test_plan = (ROOT / "docs" / "TEST_PLAN_3.1.0.md").read_text(encoding="utf-8")
        self.assertIn("ARCHITECTURE_AND_ROADMAP_3.1.0.md", readme)
        for milestone in ("3.1", "3.2", "3.3", "3.4"):
            self.assertIn(milestone, roadmap)
        self.assertIn("Whisper Medium", release)
        self.assertIn("GigaChat", release)
        self.assertIn("sherpa-onnx", release)
        self.assertIn("Озвучка", release)
        self.assertIn("Документы\\Spiker", release)
        self.assertIn("wespeaker_en_voxceleb_resnet34.onnx", test_plan)
        self.assertIn("SQLite", test_plan)

    def test_version_info_is_current(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "3.1.3")
        self.assertIn(f'#define AppVersion "{version}"', (ROOT / "installer" / "Spiker.iss").read_text(encoding="utf-8"))
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("if ($VersionParts.Count -eq 3) { $VersionParts += '0' }", build)

    def test_installer_compiler_is_resolved_before_expensive_build_steps(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        inno_check = build.index("if ($Installer) {")
        create_venv = build.index("$BuildVenv = Join-Path $Root $BuildVenvName")
        self.assertLess(inno_check, create_venv)
        self.assertIn("JRSoftware.InnoSetup", build)
        self.assertIn("Get-Command 'winget.exe'", build)
        self.assertIn("INNO_SETUP_PATH", build)
        self.assertIn("https://jrsoftware.org/isdl.php", build)


    def test_optional_installers_use_or_create_the_application_python311_venv(self):
        expected_packages = {
            "Install_Live_Dictation.bat": ("sherpa-onnx>=1.12,<2", "scripts\\download_t_one_model.py"),
            "Install_Faster_Whisper.bat": ("faster-whisper>=1.1,<2",),
            "Install_Speaker_Diarization.bat": (r"scripts\install_models.py --diarization",),
        }
        for filename, required in expected_packages.items():
            installer = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(".venv311\\Scripts\\python.exe", installer, filename)
            self.assertIn("py -3.11 -m venv", installer, filename)
            self.assertIn("sys.version_info[:2] == (3, 11)", installer, filename)
            self.assertIn('"%SPK_PYTHON%" -m pip install' if "SPK_PYTHON" in installer else '"%PYTHON%" -m pip install', installer, filename)
            for fragment in required:
                self.assertIn(fragment, installer, filename)
        model_installer = (ROOT / "scripts" / "install_models.py").read_text(encoding="utf-8")
        self.assertIn('PYANNOTE_AUDIO_VERSION = "4.0.7"', model_installer)
        self.assertIn('pyannote.audio=={PYANNOTE_AUDIO_VERSION}', model_installer)


    def test_packaged_launch_scripts_have_the_runtime_requirements_file(self):
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        self.assertIn('requirements_file = ROOT / "res" / "requirements.txt"', spec)
        self.assertIn('datas.append((str(requirements_file), "res"))', spec)

    def test_frozen_release_contains_local_voice_diarization(self):
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        guide = (ROOT / "INSTALL_WINDOWS_RU.txt").read_text(encoding="utf-8")
        self.assertIn('for source in SCRIPTS.rglob("*.py")', spec)
        self.assertIn('PySocks-1.7.1-py3-none-any.whl', spec)
        self.assertIn("ПОРТАТИВНАЯ ВЕРСИЯ", guide)
        self.assertIn("голосам", guide.lower())
        self.assertNotIn("Read-токен", guide)
        self.assertIn("Документы\\Spiker", guide)

    def test_windows_release_build_includes_streaming_t_one_by_default(self):
        batch = (ROOT / "Build_Spiker_Windows_Installer.bat").read_text(encoding="utf-8-sig")
        workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
        self.assertIn("-WithLiveDictation", batch)
        self.assertIn("-WithFasterWhisper", batch)
        self.assertIn("-WithLiveDictation", workflow)
        self.assertIn("-WithFasterWhisper", workflow)
        self.assertIn("timeout-minutes: 150", workflow)

    def test_compact_profile_builds_separate_basic_artifacts(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        installer = (ROOT / "installer" / "Spiker.iss").read_text(encoding="utf-8")
        batch = (ROOT / "Build_Spiker_Windows_Basic.bat").read_text(encoding="utf-8")
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('Full', 'Basic')][string]$Profile = 'Full'", build)
        self.assertIn("basic-stage", build)
        self.assertIn("Spiker-Portable-$Version$ArtifactSuffix.zip", build)
        self.assertIn("/DAppFolder=$InnoAppFolder", build)
        self.assertIn("OutputBaseFilename=Spiker-Setup-{#AppVersion}{#AppFlavor}", installer)
        self.assertIn("DefaultDirName={code:GetUserInstallDir}", installer)
        self.assertIn("LocalAppData := GetEnv('LOCALAPPDATA')", installer)
        self.assertIn("-Profile Basic", batch)
        self.assertIn('if exist "%~dp0.build-venv\\Scripts\\python.exe"', batch)
        self.assertIn("%BUILD_REUSE%", batch)
        self.assertIn('Spiker-Setup-$Version$ArtifactSuffix.exe', build)
        self.assertIn("-ReuseFullBuildEnvironment", build)
        self.assertIn('optional_excludes.extend(("sherpa_onnx", "onnxruntime"))', spec)
        self.assertIn('optional_excludes.extend(("faster_whisper", "ctranslate2"))', spec)

    def test_github_upload_guide_and_two_profiles_are_documented(self):
        guide = ROOT / "GITHUB_UPLOAD_RU.txt"
        self.assertTrue(guide.is_file())
        install_guide = (ROOT / "INSTALL_WINDOWS_RU.txt").read_text(encoding="utf-8")
        self.assertIn("Spiker-Models-3.1.3-Basic.zip", install_guide)
        publishing = (ROOT / "docs" / "PUBLISHING.md").read_text(encoding="utf-8")
        self.assertIn("Spiker-Setup-3.1.3-Basic.exe", publishing)
        self.assertIn("Spiker-Portable-3.1.3-Basic.zip", publishing)

    def test_gitignore_excludes_runtime_caches_and_model_weights(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for fragment in (".cache/", ".build-venv/", "dist/", "validation_samples/", "models/**/*.bin", "models/**/*.onnx"):
            self.assertIn(fragment, ignore)

    def test_user_data_is_outside_every_distribution(self):
        paths = (ROOT / "scripts" / "app_paths.py").read_text(encoding="utf-8")
        self.assertIn("destination = documents_folder() / 'Spiker'", paths)
        self.assertIn("_copy_missing_files", paths)
        self.assertIn("get_user_data_root", (ROOT / "scripts" / "app_config.py").read_text(encoding="utf-8"))

    def test_model_installer_validates_large_models_and_retries_t_one_download(self):
        installer = (ROOT / "scripts" / "install_models.py").read_text(encoding="utf-8")
        t_one_downloader = (ROOT / "scripts" / "download_t_one_model.py").read_text(encoding="utf-8")
        self.assertIn("weights.stat().st_size >= 100 * 1024 * 1024", installer)
        self.assertIn("model.stat().st_size >= 100 * 1024 * 1024", installer)
        self.assertIn("_download(MODEL_URL, archive_path, min_bytes=100 * 1024 * 1024, retries=5)", t_one_downloader)
        self.assertIn("model_file.stat().st_size >= 100 * 1024 * 1024", t_one_downloader)
        self.assertIn("def install_basic()", installer)
        self.assertIn("Продолжаем установку остальных компонентов", installer)

    def test_launcher_offers_gated_speaker_model_after_basic_setup(self):
        launcher = (ROOT / "Launch_Spiker.bat").read_text(encoding="utf-8")
        self.assertIn("--check-diarization", launcher)
        self.assertIn("--diarization", launcher)
        self.assertIn("Install automatic speaker diarization now?", launcher)
        self.assertIn("--basic", launcher)

    def test_live_optional_build_smoke_checks_sherpa_runtime_and_model(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        entry = (ROOT / "scripts" / "safe_main.py").read_text(encoding="utf-8")
        self.assertIn("--require-live-dictation", build)
        self.assertIn("--require-live-dictation", entry)
        self.assertIn('getattr(sherpa_onnx, "OnlineRecognizer", None)', entry)
        self.assertIn("model.onnx", entry)
        self.assertIn("tokens.txt", entry)


    def test_click_to_build_windows_installer_script_exists_and_builds_setup(self):
        script = ROOT / "Build_Spiker_Windows_Installer.bat"
        self.assertTrue(script.is_file())
        contents = script.read_text(encoding="utf-8-sig")
        self.assertIn("build_windows.ps1", contents)
        self.assertIn("-Installer", contents)
        self.assertIn("-WithLiveDictation", contents)
        self.assertIn("Spiker-Setup-%SPIKER_VERSION%.exe", contents)
        self.assertTrue((ROOT / "Build_Windows_Release.bat").is_file())

    def test_build_script_selects_python311_from_windows_launcher(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("function Resolve-Python311", build)
        self.assertIn("py.exe", build)
        self.assertIn("-3.11 -c", build)
        self.assertIn("& $PythonBaseExe -m venv", build)

    def test_build_hashing_uses_powershell_runtime_apis(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-Sha256Hex", build)
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", build)
        self.assertNotIn("Get-FileHash", build)



if __name__ == "__main__":
    unittest.main()
