<div align="center">
  <img src="assets/readme-banner.jpg" alt="SPIKER — local transcription and AI speech processing" width="100%">
  <p><a href="README.md">Русская версия</a></p>
</div>

<div align="center">

# SPIKER — speech to text. Simply.

**Speak, record, transcribe — SPIKER helps make the rest easier.**

A Windows desktop app for dictation, audio/video transcription, playback, and AI-assisted text processing.

[Download for Windows](#installation) · [Screenshots](#screenshots) · [Privacy](docs/PRIVACY.md) · Report bugs in this repository’s Issues section

</div>

SPIKER brings several workflows together: capture an idea, transcribe a long recording, listen to a specific part, and turn the transcript into a summary, notes, or meeting minutes.

**Less busywork — more time for what matters.**

## Features

- **Dictation:** turn microphone speech into editable, saveable text.
- **Audio/video transcription:** process multiple files in a persistent queue, pause tasks, and resume later.
- **Audio player:** listen to recordings and navigate the waveform to check long transcripts.
- **AI text processing:** create summaries and notes, structure information, extract action items, and improve formatting.
- **Local and API providers:** use local language models through Ollama or configure a supported external API.
- **Privacy-focused workflows:** speech transcription runs locally; local language-model processing stays on the device when Ollama is configured locally. External API requests send text to the selected provider.

## Screenshots

### Main menu

![SPIKER main menu](assets/screenshots/main-menu.png)

### Transcription queue and player

![Transcription queue](assets/screenshots/transcription-queue.png)

### Dictation

![Dictation screen](assets/screenshots/dictation.png)

### AI text processing

![AI processing screen](assets/screenshots/ai-processing.png)

### Help and model compatibility

![Help screen](assets/screenshots/help.png)

## Installation

1. Open the repository's **Releases** page.
2. Download **`Spiker-Setup-<version>.exe`**. Most users do not need the source ZIP or portable ZIP.
3. Run the installer and follow the prompts. Python, Qt, and the application's runtime libraries are bundled.
4. The Windows installer includes the multilingual Whisper Small model, so local speech transcription works without a model download after installation.

If `Spiker-Setup-*.exe` is not shown in Releases yet, the Windows build has not been published. See [release publishing instructions](docs/PUBLISHING.md).

### Local AI text processing

Install [Ollama for Windows](https://ollama.com/download) and download a language model before going offline, for example:

```powershell
ollama pull qwen3.5:4b
```

Large language models are not included in the base installer because of their size. An external API is optional and requires internet access.

## Technology

Python · PySide6/Qt · Whisper/whisper.cpp · optional Vosk · Ollama · Windows 10/11 x64.

## Development

See [Windows build instructions](docs/BUILD_WINDOWS.md) and [publishing guide](docs/PUBLISHING.md). The local release build uses Python 3.11 x64:

```powershell
.\build_windows.ps1 -Installer
```

The Windows release build bundles the application libraries, FFmpeg, and Whisper Small model. Ollama and language-model weights remain separate.

## Contributing

Bug reports and feature ideas are welcome. Please check the [documentation](docs/) and use the relevant [issue template](.github/ISSUE_TEMPLATE/).

## License

Source code: [Apache License 2.0](LICENSE). Third-party components and model files may have separate licensing terms; see `models/whisper/MODEL_SOURCE.md` and release notes.

*SPIKER — your words, turned into ready-to-use text.*
