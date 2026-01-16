import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

class RecordScreen extends StatefulWidget {
  final List<CameraDescription> cameras;

  const RecordScreen({Key? key, required this.cameras}) : super(key: key);

  @override
  _RecordScreenState createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> {
  CameraController? _controller;
  int _selectedCameraIndex = 0;
  bool _isInit = false;

  @override
  void initState() {
    super.initState();
    if (widget.cameras.isNotEmpty) {
      _initCamera(_selectedCameraIndex);
    }
  }

  Future<void> _initCamera(int index) async {
    final camera = widget.cameras[index];
    _controller = CameraController(
      camera,
      ResolutionPreset.high,
      enableAudio: false,
    );

    try {
      await _controller!.initialize();
      if (mounted) {
        setState(() {
          _isInit = true;
        });
      }
    } catch (e) {
      print("Camera init error: $e");
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  void _switchCamera() {
    if (widget.cameras.length < 2) return;
    setState(() {
      _isInit = false;
      _selectedCameraIndex = (_selectedCameraIndex + 1) % widget.cameras.length;
    });
    _initCamera(_selectedCameraIndex);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.cameras.isEmpty) {
      return Center(child: Text('No cameras found. Please check your device settings.'));
    }

    return Scaffold(
      body: Stack(
        children: [
          // Camera Preview
          if (_isInit && _controller != null && _controller!.value.isInitialized)
            Center(child: CameraPreview(_controller!))
          else
            Center(child: CircularProgressIndicator()),

          // Overlays
          Positioned(
            top: 20,
            left: 20,
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  Icon(Icons.circle, color: Colors.red, size: 12),
                  SizedBox(width: 8),
                  Text(
                    'Live Monitor', 
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)
                  ),
                ],
              ),
            ),
          ),

          // Camera Switcher
          if (widget.cameras.length > 1)
            Positioned(
              bottom: 30,
              right: 30,
              child: FloatingActionButton(
                onPressed: _switchCamera,
                child: Icon(Icons.cameraswitch),
                backgroundColor: Colors.white,
                foregroundColor: Colors.black,
              ),
            ),
            
          Positioned(
            bottom: 30,
            left: 0,
            right: 0,
            child: Center(
              child: Text(
                'Monitoring Stream (OBS Virtual Camera)',
                style: TextStyle(
                  color: Colors.white,
                  shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                  fontSize: 16
                ),
              ),
            ),
          )
        ],
      ),
    );
  }
}
