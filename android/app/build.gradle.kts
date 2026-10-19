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
        versionCode = (project.findProperty("versionCode") as String?)?.toInt() ?: 1
        versionName = (project.findProperty("versionName") as String?) ?: "0.2.0"
        // Server the app opens; change at build time with -PatulyaUrl=https://...
        buildConfigField("String", "ATULYA_URL", "\"${project.findProperty("atulyaUrl") ?: "https://atulya.atulvij.com"}\"")
    }
    defaultConfig {
        // Only the CI emulator smoke-test build sets -PallowScreenshots=true; released APKs keep FLAG_SECURE.
        buildConfigField("boolean", "ALLOW_SCREENSHOTS", (project.findProperty("allowScreenshots") ?: "false").toString())
        // Only the CI UI-test build talks plain http to the runner's private server (http://10.0.2.2:8501).
        manifestPlaceholders["cleartextTraffic"] = (project.findProperty("testServer") != null).toString()
    }
    buildFeatures { buildConfig = true }
    defaultConfig { resourceConfigurations += listOf("en", "hi") }
    packaging { resources.excludes += listOf("META-INF/*.version", "kotlin/**", "DebugProbesKt.bin") }
    signingConfigs {
        create("release") {
            // CI decodes the keystore from the ANDROID_KEYSTORE_B64 secret; it is never committed.
            val path = System.getenv("ANDROID_KEYSTORE_PATH")
            if (path != null) {
                storeFile = file(path)
                storeType = "PKCS12"
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = "atulya"
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            }
        }
    }
    buildTypes {
        release {
            // R8: strip unused AndroidX code and resources (no JS bridges or reflection to keep).
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("androidx.webkit:webkit:1.12.1")
}
