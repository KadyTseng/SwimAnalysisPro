# Swim Analysis Pro - Flutter Frontend

This directory contains the source code for the Flutter frontend application.

## ⚠️ Important Note
The `flutter` command was not detected in your system environment. Therefore, this project structure was generated manually.

## How to Run

1.  **Install Flutter**: Ensure you have Flutter installed and configured. [Flutter Install Guide](https://docs.flutter.dev/get-started/install/windows)
2.  **Initialize Project**:
    Open a terminal in this `frontend` directory (or parent) and run:
    ```bash
    flutter create .
    ```
    *Note: You might need to move these files into a new project if `flutter create .` fails to overwrite/merge correctly. Best practice is to create a new project `flutter create swim_app` and then copy the `lib` folder from here into it.*

3.  **Dependencies**:
    Add the following dependencies to your `pubspec.yaml`:
    ```yaml
    dependencies:
      flutter:
        sdk: flutter
      http: ^1.2.0
      file_picker: ^8.0.0
      video_player: ^2.8.0
      chewie: ^1.7.0
      percent_indicator: ^4.2.3
      intl: ^0.19.0
      path: ^1.8.3
      url_launcher: ^6.2.0
      # Add other packages as needed
    ```

4.  **Run**:
    ```bash
    flutter pub get
    flutter run
    ```

## Project Structure
- `lib/main.dart`: Entry point.
- `lib/api_service.dart`: Handles API calls to the Python backend.
- `lib/models.dart`: JSON serialization models.
- `lib/screens/`: UI screens for upload, progress, and results.
