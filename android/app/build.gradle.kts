plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "ru.spiker.mobile"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    defaultConfig { applicationId = "ru.spiker.mobile"; minSdk = 29; targetSdk = 35; versionCode = 30200; versionName = "3.1.2-mobile-preview" }
    androidResources { noCompress += listOf("onnx", "bin") }
    packaging { jniLibs.useLegacyPackaging = true }
}
dependencies { implementation(files("libs/sherpa-onnx-1.13.8.aar")) }
