package ru.spiker.mobile

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.content.ContentValues
import android.provider.MediaStore
import android.media.MediaRecorder
import android.media.MediaCodec
import android.media.MediaExtractor
import android.os.Bundle
import android.os.Environment
import android.view.Gravity
import android.view.ViewGroup
import android.widget.*
import com.k2fsa.sherpa.onnx.*
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val navy = 0xff082557.toInt()
    private val blue = 0xff147be8.toInt()
    private val cyan = 0xff32c8ff.toInt()
    private val ink = 0xffe9f4ff.toInt()
    private val worker = Executors.newSingleThreadExecutor()
    private lateinit var output: EditText
    private lateinit var input: EditText
    private lateinit var status: TextView
    private lateinit var speakerNames: EditText
    private lateinit var voice: Spinner
    private var stop = false
    private var stream: OnlineStream? = null
    private var recognizer: OnlineRecognizer? = null
    private var samples = ByteArrayOutputStream()
    private val rate = 16000

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = navy
        window.navigationBarColor = navy
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(22, 16, 22, 12); setBackgroundColor(navy) }
        val scroll = ScrollView(this)
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, 4, 0, 18) }
        scroll.addView(content)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val title = TextView(this).apply { text = "СПИКЕР"; textSize = 26f; setTextColor(ink); typeface = android.graphics.Typeface.DEFAULT_BOLD }
        content.addView(title)
        content.addView(TextView(this).apply { text = "Голос в текст · офлайн"; textSize = 14f; setTextColor(cyan); setPadding(0, 0, 0, 14) })
        content.addView(TextView(this).apply {
            text = "Мобильная версия: диктовка, озвучка и работа с аудиофайлом. Очередь Windows и обработка текста через ИИ пока недоступны."
            textSize = 12f; setTextColor(0xffb8d7f6.toInt()); setPadding(0, 0, 0, 12)
        })
        val nav = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        listOf("Диктовка", "Озвучка").forEachIndexed { i, label ->
            val b = button(label); b.setOnClickListener { if (i == 0) { scroll.smoothScrollTo(0, 0) } else { ttsPanel.requestFocus(); scroll.smoothScrollTo(0, ttsPanel.top) } }; nav.addView(b, LinearLayout.LayoutParams(0, -2, 1f))
        }
        content.addView(nav)
        content.addView(section("ПОТОКОВОЕ РАСПОЗНАВАНИЕ T-ONE"))
        val controls = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        controls.addView(button("● Начать диктовку").apply { setOnClickListener { startRecording() } }, LinearLayout.LayoutParams(0, -2, 1f))
        controls.addView(button("■ Стоп").apply { setOnClickListener { stopRecording() } }, LinearLayout.LayoutParams(0, -2, 1f))
        content.addView(controls)
        output = EditText(this).apply { hint = "Текст появится по мере речи…"; setTextColor(ink); setHintTextColor(0xff8ba9d5.toInt()); minLines = 5; gravity = Gravity.TOP; setBackgroundColor(0xff10366f.toInt()); setPadding(12, 12, 12, 12) }
        content.addView(output, margin(height = 190))
        content.addView(section("УЧАСТНИКИ"))
        speakerNames = EditText(this).apply { setSingleLine(); setText("Спикер 1, Спикер 2"); setTextColor(ink); setHintTextColor(0xff8ba9d5.toInt()); setBackgroundColor(0xff10366f.toInt()); setPadding(12, 4, 12, 4); hint = "Имена через запятую" }
        content.addView(speakerNames, margin(height = 48))
        val diarRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        diarRow.addView(button("Разделить запись").apply { setOnClickListener { separateSpeakers() } }, LinearLayout.LayoutParams(0, -2, 1f))
        diarRow.addView(button("Сохранить текст").apply { setOnClickListener { saveTranscript() } }, LinearLayout.LayoutParams(0, -2, 1f))
        content.addView(diarRow)
        ttsPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        ttsPanel.addView(section("ОЗВУЧКА · РУССКИЕ ГОЛОСА"))
        input = EditText(this).apply { hint = "Введите текст для озвучки…"; setTextColor(ink); setHintTextColor(0xff8ba9d5.toInt()); minLines = 5; gravity = Gravity.TOP; setBackgroundColor(0xff10366f.toInt()); setPadding(12, 12, 12, 12) }
        ttsPanel.addView(input, margin(height = 170))
        voice = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Ирина · женский", "Руслан · мужской")) }
        ttsPanel.addView(voice, margin())
        val speechButtons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        speechButtons.addView(button("▶ Озвучить").apply { setOnClickListener { generateSpeech() } }, LinearLayout.LayoutParams(0, -2, 1f))
        speechButtons.addView(button("TXT импорт").apply { setOnClickListener { openText() } }, LinearLayout.LayoutParams(0, -2, 1f))
        ttsPanel.addView(speechButtons)
        content.addView(ttsPanel)
        content.addView(section("ФАЙЛЫ"))
        val fileRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fileRow.addView(button("Загрузить аудио / видео").apply { setOnClickListener { openAudio() } }, LinearLayout.LayoutParams(0, -2, 1f))
        fileRow.addView(button("Загрузить текст").apply { setOnClickListener { openText() } }, LinearLayout.LayoutParams(0, -2, 1f))
        content.addView(fileRow)
        status = TextView(this).apply { text = "Модели находятся внутри приложения · интернет не нужен"; textSize = 12f; setTextColor(cyan); setPadding(0, 12, 0, 4) }
        root.addView(status)
        setContentView(root)
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 10)
    }

    private lateinit var ttsPanel: LinearLayout
    private fun section(text: String) = TextView(this).apply { this.text = text; textSize = 12f; setTextColor(cyan); setPadding(0, 16, 0, 8); letterSpacing = 0.08f }
    private fun button(text: String) = Button(this).apply { this.text = text; isAllCaps = false; setTextColor(ink); backgroundTintList = android.content.res.ColorStateList.valueOf(blue); setPadding(8, 3, 8, 3) }
    private fun margin(height: Int = -2) = LinearLayout.LayoutParams(-1, height).apply { setMargins(0, 5, 0, 6) }

    private fun asset(name: String): String {
        val dest = File(filesDir, "models/$name")
        if (dest.exists()) return dest.absolutePath
        dest.parentFile?.mkdirs()
        assets.open("models/$name").use { src -> dest.outputStream().use { src.copyTo(it) } }
        return dest.absolutePath
    }

    private fun startRecording() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 10); return }
        stop = false; samples = ByteArrayOutputStream(); output.setText(""); status.text = "Загружаем голосовую модель…"
        worker.execute {
            try {
                val model = asset("t-one/model.onnx"); val tokens = asset("t-one/tokens.txt")
                val cfg = OnlineRecognizerConfig(
                    featConfig = FeatureConfig(sampleRate = 8000, featureDim = 80),
                    modelConfig = OnlineModelConfig(toneCtc = OnlineToneCtcModelConfig(model), tokens = tokens, numThreads = 2, provider = "cpu"),
                    enableEndpoint = true, decodingMethod = "greedy_search")
                recognizer = OnlineRecognizer(config = cfg); stream = recognizer!!.createStream()
                val size = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT).coerceAtLeast(4096)
                val record = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, size)
                record.startRecording(); runOnUiThread { status.text = "Слушаю микрофон…" }
                val buffer = ShortArray(1600)
                while (!stop) {
                    val read = record.read(buffer, 0, buffer.size)
                    if (read <= 0) continue
                    val raw = ByteBuffer.allocate(read * 2).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer(); raw.put(buffer, 0, read)
                    val bytes = ByteArray(read * 2); ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(buffer, 0, read); synchronized(samples) { samples.write(bytes) }
                    val pcm = FloatArray(read) { buffer[it].toFloat() / 32768f }
                    val active = stream!!; active.acceptWaveform(pcm, rate)
                    while (recognizer!!.isReady(active)) recognizer!!.decode(active)
                    val text = recognizer!!.getResult(active).text
                    runOnUiThread { output.setText(text); output.setSelection(output.text.length) }
                    if (recognizer!!.isEndpoint(active)) recognizer!!.reset(active)
                }
                record.stop(); record.release()
                runOnUiThread { status.text = "Запись остановлена. Можно разделить голоса или сохранить текст." }
            } catch (e: Exception) { runOnUiThread { status.text = "Ошибка микрофона/модели: ${e.message}" } }
        }
    }

    private fun stopRecording() { stop = true }

    private fun openAudio() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { type = "*/*"; putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("audio/*", "video/*")); addCategory(Intent.CATEGORY_OPENABLE) }, 21)
    }

    private fun saveTranscript() {
        val text = output.text.toString().trim()
        if (text.isEmpty()) { status.text = "Нет текста для сохранения."; return }
        try {
            val values = ContentValues().apply { put(MediaStore.MediaColumns.DISPLAY_NAME, "spiker-${System.currentTimeMillis()}.txt"); put(MediaStore.MediaColumns.MIME_TYPE, "text/plain"); put(MediaStore.MediaColumns.RELATIVE_PATH, "Documents/Spiker") }
            val uri = contentResolver.insert(MediaStore.Files.getContentUri("external"), values) ?: error("Не удалось создать документ")
            contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use { it.write(text) }
            status.text = "Текст сохранён в Документы/Spiker"
        } catch (e: Exception) { status.text = "Ошибка сохранения: ${e.message}" }
    }

    private fun transcribeAudio(uri: android.net.Uri) {
        status.text = "Открываем аудиодорожку…"
        worker.execute {
            try {
                val pcm = decodeAudio(uri)
                synchronized(samples) { samples.reset(); samples.write(pcm) }
                val text = recognizePcm(pcm)
                runOnUiThread { output.setText(text); status.text = "Файл распознан офлайн. Теперь можно разделить голоса." }
            } catch (e: Exception) { runOnUiThread { status.text = "Не удалось распознать файл: ${e.message}" } }
        }
    }

    private fun recognizePcm(pcm: ByteArray): String {
        val model = asset("t-one/model.onnx"); val tokens = asset("t-one/tokens.txt")
        val cfg = OnlineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 8000, featureDim = 80),
            modelConfig = OnlineModelConfig(toneCtc = OnlineToneCtcModelConfig(model), tokens = tokens, numThreads = 2, provider = "cpu"),
            enableEndpoint = true, decodingMethod = "greedy_search")
        val engine = OnlineRecognizer(config = cfg); val decoder = engine.createStream()
        try {
            var committed = ""; var offset = 0
            while (offset < pcm.size) {
                val count = minOf(3200, pcm.size - offset) / 2
                if (count <= 0) break
                val block = FloatArray(count) { ByteBuffer.wrap(pcm, offset + it * 2, 2).order(ByteOrder.LITTLE_ENDIAN).short / 32768f }
                decoder.acceptWaveform(block, rate)
                while (engine.isReady(decoder)) engine.decode(decoder)
                val phrase = engine.getResult(decoder).text
                if (engine.isEndpoint(decoder)) { if (phrase.isNotBlank()) committed = "$committed $phrase".trim(); engine.reset(decoder) }
                runOnUiThread { output.setText((committed + " " + phrase).trim()) }
                offset += count * 2
            }
            decoder.inputFinished()
            while (engine.isReady(decoder)) engine.decode(decoder)
            return (committed + " " + engine.getResult(decoder).text).trim()
        } finally { decoder.release(); engine.release() }
    }

    private fun decodeAudio(uri: android.net.Uri): ByteArray {
        val extractor = MediaExtractor()
        contentResolver.openAssetFileDescriptor(uri, "r")?.use { extractor.setDataSource(it.fileDescriptor, it.startOffset, it.length) }
            ?: error("Не удалось открыть файл")
        var track = -1
        for (i in 0 until extractor.trackCount) if (extractor.getTrackFormat(i).getString(android.media.MediaFormat.KEY_MIME)?.startsWith("audio/") == true) { track = i; break }
        if (track < 0) error("В файле не найдена аудиодорожка")
        extractor.selectTrack(track)
        val format = extractor.getTrackFormat(track); val mime = format.getString(android.media.MediaFormat.KEY_MIME)!!
        val codec = MediaCodec.createDecoderByType(mime); codec.configure(format, null, null, 0); codec.start()
        val channels = format.getInteger(android.media.MediaFormat.KEY_CHANNEL_COUNT); val sourceRate = format.getInteger(android.media.MediaFormat.KEY_SAMPLE_RATE)
        val output = ByteArrayOutputStream(); val info = MediaCodec.BufferInfo(); var inputDone = false; var outputDone = false
        try {
            while (!outputDone) {
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(10000)
                    if (index >= 0) {
                        val buffer = codec.getInputBuffer(index)!!; val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) { codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM); inputDone = true }
                        else { codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0); extractor.advance() }
                    }
                }
                val index = codec.dequeueOutputBuffer(info, 10000)
                if (index >= 0) {
                    val buffer = codec.getOutputBuffer(index)!!
                    if (info.size > 0) {
                        buffer.position(info.offset); buffer.limit(info.offset + info.size)
                        val shorts = buffer.slice().order(ByteOrder.LITTLE_ENDIAN).asShortBuffer(); val frameCount = shorts.remaining() / channels
                        val mono = ShortArray(frameCount)
                        for (frame in 0 until frameCount) { var sum = 0; for (channel in 0 until channels) sum += shorts.get(); mono[frame] = (sum / channels).toShort() }
                        val targetCount = (frameCount.toLong() * rate / sourceRate).toInt(); val target = ByteBuffer.allocate(targetCount * 2).order(ByteOrder.LITTLE_ENDIAN)
                        for (i in 0 until targetCount) { val src = i.toDouble() * sourceRate / rate; val lo = src.toInt().coerceAtMost(frameCount - 1); val hi = (lo + 1).coerceAtMost(frameCount - 1); val fraction = src - lo; target.putShort((mono[lo] * (1 - fraction) + mono[hi] * fraction).toInt().toShort()) }
                        output.write(target.array())
                    }
                    outputDone = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0; codec.releaseOutputBuffer(index, false)
                }
            }
        } finally { codec.stop(); codec.release(); extractor.release() }
        if (output.size() < rate * 2) error("Аудиодорожка слишком короткая или пуста")
        return output.toByteArray()
    }

    private fun separateSpeakers() {
        val pcm = synchronized(samples) { samples.toByteArray() }
        if (pcm.size < rate * 2) { status.text = "Сначала запишите несколько секунд речи."; return }
        status.text = "Анализируем голоса…"
        worker.execute {
            try {
                val floats = FloatArray(pcm.size / 2) { ByteBuffer.wrap(pcm, it * 2, 2).order(ByteOrder.LITTLE_ENDIAN).short / 32768f }
                val config = OfflineSpeakerDiarizationConfig(
                    segmentation = OfflineSpeakerSegmentationModelConfig(pyannote = OfflineSpeakerSegmentationPyannoteModelConfig(asset("diarization/model.onnx")), numThreads = 2),
                    embedding = SpeakerEmbeddingExtractorConfig(asset("diarization/embedding.onnx"), numThreads = 2),
                    clustering = FastClusteringConfig(numClusters = -1, threshold = .5f))
                val engine = OfflineSpeakerDiarization(config = config)
                val turns = engine.process(floats).sortedBy { it.start }
                val names = speakerNames.text.toString().split(',').map { it.trim() }.filter { it.isNotEmpty() }
                val labels = turns.map { turn ->
                    val name = names.getOrElse(turn.speaker) { "Спикер ${turn.speaker + 1}" }
                    "$name · ${"%.1f".format(turn.start)}–${"%.1f".format(turn.end)} с"
                }
                engine.release()
                runOnUiThread { status.text = if (labels.isEmpty()) "Не нашёл голосовых интервалов." else labels.distinct().joinToString("\n"); }
            } catch (e: Exception) { runOnUiThread { status.text = "Не удалось разделить голоса: ${e.message}" } }
        }
    }

    private fun generateSpeech() {
        val text = input.text.toString().trim(); if (text.isEmpty()) { status.text = "Введите текст."; return }
        status.text = "Создаём русскую озвучку…"
        worker.execute {
            try {
                val v = if (voice.selectedItemPosition == 0) "irina" else "ruslan"
                val dir = "tts/$v"
                val config = OfflineTtsConfig(model = OfflineTtsModelConfig(vits = OfflineTtsVitsModelConfig(
                    model = asset("$dir/ru_RU-$v-medium.onnx"), tokens = asset("$dir/tokens.txt"), dataDir = asset("$dir/espeak-ng-data")), numThreads = 2))
                val tts = OfflineTts(config = config); val chunks = text.chunked(280); val outputSamples = ArrayList<Float>(); var sampleRate = 22050
                for (chunk in chunks) { val audio = tts.generate(chunk); sampleRate = audio.sampleRate; outputSamples.addAll(audio.samples.toList()) }
                tts.release()
                val values = ContentValues().apply { put(MediaStore.MediaColumns.DISPLAY_NAME, "spiker-${System.currentTimeMillis()}.wav"); put(MediaStore.MediaColumns.MIME_TYPE, "audio/wav"); put(MediaStore.MediaColumns.RELATIVE_PATH, "Documents/Spiker") }
                val uri = contentResolver.insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, values) ?: error("Не удалось создать WAV в Documents/Spiker")
                val floatSamples = outputSamples.toFloatArray()
                contentResolver.openOutputStream(uri)?.use { writeWav(it, floatSamples, sampleRate) } ?: error("Не удалось записать WAV")
                val track = AudioTrack.Builder().setAudioAttributes(android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_MEDIA).setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build()).setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_FLOAT).setSampleRate(sampleRate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build()).setBufferSizeInBytes(outputSamples.size * 4).setTransferMode(AudioTrack.MODE_STATIC).build()
                track.write(outputSamples.toFloatArray(), 0, outputSamples.size, AudioTrack.WRITE_BLOCKING); track.play()
                runOnUiThread { status.text = "Готово · Документы/Spiker · ${uri.lastPathSegment}" }
            } catch (e: Exception) { runOnUiThread { status.text = "Ошибка озвучки: ${e.message}" } }
        }
    }

    private fun writeWav(out: java.io.OutputStream, samples: FloatArray, sampleRate: Int) {
        val pcm = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        samples.forEach { pcm.putShort((it.coerceIn(-1f, 1f) * 32767).toInt().toShort()) }
        run {
            val data = pcm.array(); val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
            header.put("RIFF".toByteArray()); header.putInt(36 + data.size); header.put("WAVEfmt ".toByteArray()); header.putInt(16); header.putShort(1); header.putShort(1); header.putInt(sampleRate); header.putInt(sampleRate * 2); header.putShort(2); header.putShort(16); header.put("data".toByteArray()); header.putInt(data.size); out.write(header.array()); out.write(data)
        }
    }

    private fun openText() { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { type = "text/*"; addCategory(Intent.CATEGORY_OPENABLE) }, 20) }
    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) { super.onActivityResult(requestCode, resultCode, data); if (resultCode == Activity.RESULT_OK) data?.data?.let { uri -> if (requestCode == 20) try { contentResolver.openInputStream(uri)?.bufferedReader()?.use { input.setText(it.readText()) } } catch (e: Exception) { status.text = "Не удалось открыть текст: ${e.message}" } else if (requestCode == 21) transcribeAudio(uri) } }
    override fun onDestroy() { stop = true; try { stream?.release(); recognizer?.release() } catch (_: Exception) {}; worker.shutdownNow(); super.onDestroy() }
}
