// import 'package:flutter/material.dart';
// import 'package:camera/camera.dart';
// import 'screen_share.dart';

// class RecordScreen extends StatefulWidget {
//   final List<CameraDescription> cameras;

//   const RecordScreen({Key? key, required this.cameras}) : super(key: key);

//   @override
//   _RecordScreenState createState() => _RecordScreenState();
// }

// class _RecordScreenState extends State<RecordScreen> {
//   CameraController? _controller;
//   int _selectedCameraIndex = 0;
//   bool _isInit = false;
//   bool _useScreenShare = false;

//   @override
//   void initState() {
//     super.initState();
//     if (widget.cameras.isNotEmpty) {
//       _initCamera(_selectedCameraIndex);
//     }
//   }

//   Future<void> _initCamera(int index) async {
//     final camera = widget.cameras[index];
//     _controller = CameraController(
//       camera,
//       ResolutionPreset.high,
//       enableAudio: false,
//     );

//     try {
//       await _controller!.initialize();
//       if (mounted) {
//         setState(() {
//           _isInit = true;
//           _useScreenShare = false; // Successfully initialized camera
//         });
//       }
//     } catch (e) {
//       print("Camera init error: $e");
//       if (mounted) {
//         setState(() {
//           _useScreenShare = true; // Fallback to screen share
//           _isInit = false;
//         });
//       }
//     }
//   }

//   @override
//   void dispose() {
//     _controller?.dispose();
//     super.dispose();
//   }

//   void _switchCamera() {
//     if (widget.cameras.length < 2) return;
//     setState(() {
//       _isInit = false;
//       _selectedCameraIndex = (_selectedCameraIndex + 1) % widget.cameras.length;
//     });
//     _initCamera(_selectedCameraIndex);
//   }

//   @override
//   Widget build(BuildContext context) {
//     if (widget.cameras.isEmpty && !_useScreenShare) {
//       return Center(
//         child: Column(
//           mainAxisSize: MainAxisSize.min,
//           children: [
//             Text('No cameras found. Please check your device settings.'),
//             SizedBox(height: 16),
//             ElevatedButton(
//               onPressed: () {
//                 setState(() {
//                   _useScreenShare = true;
//                 });
//               },
//               child: Text("Try Screen Sharing"),
//             )
//           ],
//         )
//       );
//     }

//     return Scaffold(
//       body: Stack(
//         children: [
//           // Content Area
//           if (_useScreenShare)
//             ScreenShareView(
//               onStop: () {
//                 setState(() {
//                   _useScreenShare = false;
//                 });
//               },
//             )
//           else if (_isInit && _controller != null && _controller!.value.isInitialized)
//             Center(child: CameraPreview(_controller!))
//           else
//             Center(child: CircularProgressIndicator()),

//           // Overlays
//           Positioned(
//             top: 20,
//             left: 20,
//             child: Container(
//               padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
//               decoration: BoxDecoration(
//                 color: Colors.black54,
//                 borderRadius: BorderRadius.circular(20),
//               ),
//               child: Row(
//                 children: [
//                   Icon(Icons.circle, color: Colors.red, size: 12),
//                   SizedBox(width: 8),
//                   Text(
//                     'Live Monitor', 
//                     style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)
//                   ),
//                 ],
//               ),
//             ),
//           ),

//           // Mode Switcher (Screen Share vs Camera)
//           Positioned(
//             bottom: 30,
//             right: widget.cameras.length > 1 ? 100 : 30, // Offset if camera switcher exists
//             child: FloatingActionButton(
//               heroTag: 'modeSwitcher',
//               onPressed: () {
//                 if (_useScreenShare) {
//                   setState(() => _useScreenShare = false);
//                   if (!_isInit) _initCamera(_selectedCameraIndex);
//                 } else {
//                   setState(() {
//                     _useScreenShare = true;
//                   });
//                 }
//               },
//               backgroundColor: _useScreenShare ? Colors.red : Colors.blue,
//               foregroundColor: Colors.white,
//               tooltip: _useScreenShare ? 'Stop Screen Share' : 'Start Screen Share',
//               child: Icon(_useScreenShare ? Icons.stop_screen_share : Icons.screen_share),
//             ),
//           ),
            
//           // Camera Switcher
//           if (widget.cameras.length > 1 && !_useScreenShare)
//             Positioned(
//               bottom: 30,
//               right: 30,
//               child: FloatingActionButton(
//                 heroTag: 'cameraSwitcher',
//                 onPressed: _switchCamera,
//                 child: Icon(Icons.cameraswitch),
//                 backgroundColor: Colors.white,
//                 foregroundColor: Colors.black,
//               ),
//             ),
            
//           Positioned(
//             bottom: 30,
//             left: 0,
//             right: 0,
//             child: Center(
//               child: Text(
//                 'Monitoring Stream (OBS Virtual Camera)',
//                 style: TextStyle(
//                   color: Colors.white,
//                   shadows: [Shadow(color: Colors.black, blurRadius: 4)],
//                   fontSize: 16
//                 ),
//               ),
//             ),
//           )
//         ],
//       ),
//     );
//   }
// }






import 'package:flutter/material.dart';
import 'screen_share.dart';
import 'dart:html'as html;
import 'dart:ui' as ui;

class RecordScreen extends StatefulWidget {
  const RecordScreen({Key? key}) : super(key: key);

  @override
  _RecordScreenState createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> {
  html.VideoElement? _videoElement;
  List<html.MediaDeviceInfo> _cameras = [];

  int _selectedCameraIndex = 0;
  bool _isInit = false;
  bool _useScreenShare = false;

  final String _viewType = "cameraVideo";

  @override
  void initState() {
    super.initState();
    _getAllCameras();
  }

  /// 取得所有 camera
  Future<void> _getAllCameras() async {
    try {
      // 先取得權限
      await html.window.navigator.mediaDevices!.getUserMedia({
        'video': true,
        'audio': false,
      });

      final devices =
          await html.window.navigator.mediaDevices?.enumerateDevices();
      _cameras = devices!.where((device) => device.kind == 'videoinput').cast<html.MediaDeviceInfo>().toList();

      if (_cameras.isNotEmpty) {
        await _initCamera(0);
      } else {
        setState(() {
          _useScreenShare = true;
        });
      }
    } catch (e) {
      print("Camera enumerate error: $e");
      setState(() {
        _useScreenShare = true;
      });
    }
  }

    /// 初始化 camera
  Future<void> _initCamera(int index) async {
    try {
      final camera = _cameras[index];

      final constraints = {
        'video': {
          'deviceId': camera.deviceId,
          'width': {'ideal': 1280},
          'height': {'ideal': 720},
        },
        'audio': false,
      };

      final stream = await html.window.navigator.mediaDevices!
          .getUserMedia(constraints);

      _videoElement = html.VideoElement()
        ..srcObject = stream
        ..autoplay = true
        ..muted = true
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.objectFit = 'cover';

      // ignore: undefined_prefixed_name
      ui.platformViewRegistry.registerViewFactory(
        _viewType,
        (int viewId) => _videoElement!,
      );

      if (mounted) {
        setState(() {
          _selectedCameraIndex = index;
          _isInit = true;
          _useScreenShare = false;
        });
      }
    } catch (e) {
      print("Camera init error: $e");

      if (mounted) {
        setState(() {
          _useScreenShare = true;
          _isInit = false;
        });
      }
    }
  }

 /// 切換 camera
  void _switchCamera() {
    if (_cameras.length < 2) return;

    final newIndex = (_selectedCameraIndex + 1) % _cameras.length;

    setState(() {
      _isInit = false;
    });

    _initCamera(newIndex);
  }


  /// 停止 camera stream
  void _stopCamera() {
    final stream = _videoElement?.srcObject as html.MediaStream?;

    if (stream != null) {
      for (var track in stream.getTracks()) {
        track.stop();
      }
    }
  }

  @override
  void dispose() {
    _stopCamera();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_cameras.isEmpty && !_useScreenShare) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('No cameras found. Please check permissions.'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  _useScreenShare = true;
                });
              },
              child: const Text("Try Screen Sharing"),
            )
          ],
        ),
      );
    }

    return Scaffold(
      body: Stack(
        children: [
          /// Camera / ScreenShare 畫面
          if (_useScreenShare)
            ScreenShareView(
              onStop: () {
                setState(() {
                  _useScreenShare = false;
                });

                if (!_isInit) {
                  _initCamera(_selectedCameraIndex);
                }
              },
            )
          else if (_isInit)
            Center(
              child: HtmlElementView(viewType: _viewType),
            )
          else
            const Center(child: CircularProgressIndicator()),

          /// 左上角 LIVE
          Positioned(
            top: 20,
            left: 20,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Row(
                children: [
                  Icon(Icons.circle, color: Colors.red, size: 12),
                  SizedBox(width: 8),
                  Text(
                    'Live Monitor',
                    style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),

          /// Screen share 按鈕
          Positioned(
            bottom: 30,
            right: _cameras.length > 1 ? 100 : 30,
            child: FloatingActionButton(
              heroTag: 'modeSwitcher',
              onPressed: () {
                if (_useScreenShare) {
                  setState(() => _useScreenShare = false);

                  if (!_isInit) {
                    _initCamera(_selectedCameraIndex);
                  }
                } else {
                  setState(() {
                    _useScreenShare = true;
                  });
                }
              },
              backgroundColor:
                  _useScreenShare ? Colors.red : Colors.blue,
              foregroundColor: Colors.white,
              child: Icon(_useScreenShare
                  ? Icons.stop_screen_share
                  : Icons.screen_share),
            ),
          ),

          /// Camera 切換
          if (_cameras.length > 1 && !_useScreenShare)
            Positioned(
              bottom: 30,
              right: 30,
              child: FloatingActionButton(
                heroTag: 'cameraSwitcher',
                onPressed: _switchCamera,
                child: const Icon(Icons.cameraswitch),
                backgroundColor: Colors.white,
                foregroundColor: Colors.black,
              ),
            ),

          /// 底部文字
          const Positioned(
            bottom: 30,
            left: 0,
            right: 0,
            child: Center(
              child: Text(
                'Monitoring Stream (OBS Virtual Camera)',
                style: TextStyle(
                    color: Colors.white,
                    shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                    fontSize: 16),
              ),
            ),
          )
        ],
      ),
    );
  }
}