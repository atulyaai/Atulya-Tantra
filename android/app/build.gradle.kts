plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.atulvij.atulya"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.atulvij.atulya"
        minSdk = 28
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
        // Server the app opens; change at build time with -PatulyaUrl=https://...
        buildConfigField("String", "ATULYA_URL", "\"${project.findProperty("atulyaUrl") ?: "https://atulya.atulvij.com"}\"")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("androidx.webkit:webkit:1.11.0")
}
