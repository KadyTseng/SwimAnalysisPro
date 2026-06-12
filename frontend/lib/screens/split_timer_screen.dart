import 'package:flutter/material.dart';
import '../api_service.dart';
import 'dart:html' as html;
import 'dart:ui' as ui;
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:js' as js;

class _LapState {
  final int lapNumber;
  Duration? splitTime; 
  Duration remainingTime; 
  bool isRunning; 
  bool isCompleted; 

  _LapState({
    required this.lapNumber,
    this.splitTime,
    this.remainingTime = const Duration(minutes: 2),
    this.isRunning = false,
    this.isCompleted = false,
  });
}

class SplitTimerScreen extends StatefulWidget {
  final Function(int, {String? videoId, dynamic uploadFile})? onNavigate;
  final bool isActive;

  const SplitTimerScreen({Key? key, this.onNavigate, this.isActive = true}) : super(key: key);

  @override
  _SplitTimerScreenState createState() => _SplitTimerScreenState();
}

class _SplitTimerScreenState extends State<SplitTimerScreen> with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  html.VideoElement? _videoElement;
  List<html.MediaDeviceInfo> _cameras = [];
  int _selectedCameraIndex = 0;
  bool _isInit = false;
  final String _viewType = "cameraVideo_split";

  // OBS WebSocket & State
  html.WebSocket? _obsSocket;
  bool _obsConnected = false;
  bool _obsRecording = false;
  bool _vcamActive = false;
  bool _isCalibrationOpen = false;

  // Real-time Detection WebSocket & Frame Streaming
  html.WebSocket? _realtimeSocket;
  Timer? _frameTimer;

  // Real-time Detection Status
  List<int> _roiX = [3600, 3650];
  List<int> _roiY = [580, 750];
  bool _roiShifted = false;
  bool _inCooldown = false;
  double _detectorScore = 0.0;
  double _detectorThreshold = 6.0;
  String _detectorChannel = 'green';

  // History buffers for real-time waveform plotting (up to 150 points)
  final List<double> _chartRHistory = [];
  final List<double> _chartGHistory = [];
  final List<double> _chartBHistory = [];
  final List<double> _chartScoreHistory = [];
  StateSetter? _dialogSetState;

  // Custom channel directions and references (swim_split_timer_Dynamic.py)
  int _blueVar = 0;
  int _greenVar = 0;
  int _redVar = 0;
  double _refR = 0.0;
  double _refG = 0.0;
  double _refB = 0.0;
  bool _isLocked = false;
  List<int> _lockedCombo = [0, 0, 0];

  // Split Timer States & Lap States
  int _targetLaps = 4;
  bool _hasSelectedLaps = false;
  List<_LapState> _laps = [];
  int _currentLapIndex = 0;
  int? _lastWarningSecond;
  DateTime? _lapStartTime;
  
  List<Duration> _lapTimes = [];
  Stopwatch _stopwatch = Stopwatch();
  Timer? _stopwatchTimer;
  Duration _totalElapsed = Duration.zero;
  bool _isRunning = false;
  bool _lastTriggerState = false;

  // Browser-side recording
  html.MediaRecorder? _mediaRecorder;
  List<html.Blob> _recordedChunks = [];
  bool _isAutoUploading = false;
  String? _completionStatus;
  DateTime? _recordingStartTime;
  html.CanvasElement? _recordingCanvas;
  html.CanvasRenderingContext2D? _recordingCtx;
  html.CanvasElement? _sendFrameCanvas;
  html.CanvasRenderingContext2D? _sendFrameCtx;
  bool _isRecordingCanvasLoopRunning = false;

  // Floating notification message
  String? _bottomRightMessage;
  Timer? _bottomRightMessageTimer;

  // Countdown timer before starting
  int _countdownValue = 0;
  bool _isCountingDown = false;
  Timer? _countdownTimer;
  html.AudioElement? _activeAudioElement;
  js.JsObject? _audioContext;

  @override
  void initState() {
    super.initState();
    _getAllCameras();
    _connectObs();
    _connectRealtimeWs();
  }

  @override
  void dispose() {
    _stopCamera();
    _frameTimer?.cancel();
    _stopwatchTimer?.cancel();
    _countdownTimer?.cancel();
    _activeAudioElement?.pause();
    _obsSocket?.close();
    _realtimeSocket?.close();
    super.dispose();
  }

  // --- Dynamic Base URL helper ---
  String _getDynamicBaseUrl() {
    final origin = html.window.location.origin;
    if (origin.startsWith('https://')) {
      return 'https://catslab.ee.ncku.edu.tw/swimming_analysis/api';
    }
    if (origin.contains(':19191')) {
      return origin.replaceAll(':19191', ':18181');
    }
    return 'http://127.0.0.1:18181';
  }

  String _getRealtimeWsUrl() {
    final baseUrl = _getDynamicBaseUrl();
    if (baseUrl.startsWith('https://')) {
      return baseUrl.replaceAll('https://', 'wss://') + '/analysis/realtime';
    } else {
      return baseUrl.replaceAll('http://', 'ws://') + '/analysis/realtime';
    }
  }

  // --- Real-time detection WS & Frame Streaming ---
  void _connectRealtimeWs() {
    _realtimeSocket?.close();
    final wsUrl = _getRealtimeWsUrl();
    print('Connecting to Real-time Detection WebSocket: $wsUrl');

    try {
      _realtimeSocket = html.WebSocket(wsUrl);

      _realtimeSocket!.onOpen.listen((e) {
        print('Real-time Detection WebSocket opened.');
        _sendConfigToBackend(); // 同步當前已調整的校正參數至後端
        if (_isRunning) {
          _startStreaming();
        }
      });

      _realtimeSocket!.onMessage.listen((e) {
        final data = jsonDecode(e.data);
        if (data['event'] == 'status') {
          final bool triggered = data['triggered'] ?? false;
          final double score = (data['score'] ?? 0.0).toDouble();
          final double rawR = (data['raw_r'] ?? 0.0).toDouble();
          final double rawG = (data['raw_g'] ?? 0.0).toDouble();
          final double rawB = (data['raw_b'] ?? 0.0).toDouble();
          final double refR = (data['ref_r'] ?? 0.0).toDouble();
          final double refG = (data['ref_g'] ?? 0.0).toDouble();
          final double refB = (data['ref_b'] ?? 0.0).toDouble();

          setState(() {
            _roiX = List<int>.from(data['roi_x'] ?? [3200, 3300]);
            _roiY = List<int>.from(data['roi_y'] ?? [630, 800]);
            _roiShifted = data['roi_shifted'] ?? false;
            _inCooldown = data['in_cooldown'] ?? false;
            _detectorScore = score;
            _refR = refR;
            _refG = refG;
            _refB = refB;
            
            _isLocked = data['is_locked'] ?? false;
            _lockedCombo = List<int>.from(data['locked_combo'] ?? [0, 0, 0]);
            if (_lockedCombo.length >= 3) {
              _blueVar = _lockedCombo[0];
              _greenVar = _lockedCombo[1];
              _redVar = _lockedCombo[2];
            }

            _chartRHistory.add(rawR);
            _chartGHistory.add(rawG);
            _chartBHistory.add(rawB);
            _chartScoreHistory.add(score);

            if (_chartRHistory.length > 150) {
              _chartRHistory.removeAt(0);
              _chartGHistory.removeAt(0);
              _chartBHistory.removeAt(0);
              _chartScoreHistory.removeAt(0);
            }
          });

          if (_dialogSetState != null) {
            _dialogSetState!(() {});
          }

          // Rising edge trigger detection
          if (triggered && !_lastTriggerState) {
            _onSwimmerCrossed();
          }
          _lastTriggerState = triggered;
        } else if (data['event'] == 'triggered') {
          _onSwimmerCrossed();
        }
      });

      _realtimeSocket!.onClose.listen((e) {
        print('Real-time Detection WebSocket closed. Reconnecting in 3s...');
        _stopStreaming();
        Future.delayed(const Duration(seconds: 3), () {
          if (mounted) _connectRealtimeWs();
        });
      });
    } catch (err) {
      print('Real-time WS connection exception: $err');
    }
  }

  void _startStreaming() {
    print("DEBUG: _startStreaming() called! Starting periodic timer.");
    _frameTimer?.cancel();
    _frameTimer = Timer.periodic(const Duration(milliseconds: 16), (timer) { // ~60 FPS
      _sendFrame();
    });
    setState(() {});
  }

  void _stopStreaming() {
    print("DEBUG: _stopStreaming() called! Cancelling timer.");
    _frameTimer?.cancel();
    _frameTimer = null;
    _chartRHistory.clear();
    _chartGHistory.clear();
    _chartBHistory.clear();
    _chartScoreHistory.clear();
    setState(() {});
  }

  void _sendFrame() {
    if (_videoElement == null || _realtimeSocket == null || _realtimeSocket!.readyState != html.WebSocket.OPEN) {
      print("DEBUG: _sendFrame aborted early! videoElement is ${_videoElement == null ? 'NULL' : 'OK'}, socket is ${_realtimeSocket == null ? 'NULL' : 'ReadyState ' + (_realtimeSocket?.readyState).toString()}");
      return;
    }
    if (_videoElement!.videoWidth == 0 || _videoElement!.videoHeight == 0) {
      print("DEBUG: _sendFrame aborted early! video dimensions are 0x0.");
      return;
    }

    print("DEBUG: _sendFrame executing successfully! Width=${_videoElement!.videoWidth}, Height=${_videoElement!.videoHeight}");

    try {
      if (_sendFrameCanvas == null) {
        _sendFrameCanvas = html.CanvasElement(width: 80, height: 45);
        _sendFrameCtx = _sendFrameCanvas!.context2D;
      }
      _sendFrameCtx!.drawImageScaled(_videoElement!, 0, 0, 80, 45);

      // toBlob is completely asynchronous and does not block the UI thread or stall the GPU presentation!
      _sendFrameCanvas!.toBlob('image/jpeg').then((blob) {
        final reader = html.FileReader();
        reader.onLoadEnd.listen((e) {
          final String? dataUrl = reader.result as String?;
          if (dataUrl != null && _realtimeSocket != null && _realtimeSocket!.readyState == html.WebSocket.OPEN) {
            _realtimeSocket!.sendString(dataUrl);
          }
        });
        reader.readAsDataUrl(blob);
      });
    } catch (e) {
      print("Error sending frame: $e");
    }
  }

  // --- OBS WebSocket Connection ---
  void _connectObs() {
    try {
      _obsSocket = html.WebSocket('ws://127.0.0.1:4455');
      _obsSocket!.onOpen.listen((e) {
        print('OBS WebSocket connection opened (Split Timer).');
      });

      _obsSocket!.onMessage.listen((e) {
        final data = jsonDecode(e.data);
        final op = data['op'];

        if (op == 0) { // Hello
          _obsSocket!.sendString(jsonEncode({
            'op': 1,
            'd': {
              'rpcVersion': 1,
              'eventSubscriptions': (1 << 6) // Outputs (Recording)
            }
          }));
        } else if (op == 2) { // Identified
          setState(() {
            _obsConnected = true;
          });
          print('OBS WebSocket Identified successfully (Split Timer)!');

          // Check Virtual Camera status
          _obsSocket!.sendString(jsonEncode({
            'op': 6,
            'd': {
              'requestType': 'GetVirtualCamStatus',
              'requestId': 'get_vcam'
            }
          }));

          // Check current Recording status
          _obsSocket!.sendString(jsonEncode({
            'op': 6,
            'd': {
              'requestType': 'GetRecordStatus',
              'requestId': 'get_record_status'
            }
          }));
        } else if (op == 7) { // RequestResponse
          final d = data['d'];
          final requestId = d['requestId'];
          if (requestId == 'get_vcam') {
            final responseData = d['responseData'] ?? {};
            setState(() {
              _vcamActive = responseData['virtualCamIsActive'] ?? false;
            });
          } else if (requestId == 'get_record_status') {
            final responseData = d['responseData'] ?? {};
            final bool isRecording = responseData['outputActive'] ?? false;
            if (isRecording) {
              _obsSocket!.sendString(jsonEncode({
                'op': 6,
                'd': {
                  'requestType': 'StopRecord',
                  'requestId': 'stop_record_on_init'
                }
              }));
              print("OBS was recording on init/refresh. Stopped it to reset to idle state.");
            }
            setState(() {
              _obsRecording = false;
            });
          }
        } else if (op == 5) { // Event
          final d = data['d'];
          final eventType = d['eventType'];
          final eventData = d['eventData'] ?? {};

          if (eventType == 'RecordStateChanged') {
            final bool isActive = eventData['outputActive'] ?? false;
            setState(() {
              _obsRecording = isActive;
            });
            print('OBS Recording State Changed (Split): $_obsRecording');

            if (!widget.isActive) {
              print('SplitTimerScreen (Background): Sync _obsRecording state only.');
              return;
            }

            if (!isActive) {
              print("OBS recording stopped. Syncing state...");
              if (_mediaRecorder != null && _mediaRecorder!.state == 'recording') {
                _mediaRecorder!.stop();
              }
              final currentLap = _laps.isNotEmpty && _currentLapIndex < _laps.length 
                  ? _laps[_currentLapIndex] 
                  : null;
              if (currentLap != null && !currentLap.isCompleted) {
                // If the swimmer has not crossed yet, it's a manual stop of the entire timing/recording session!
                // We ignore delayed stop events from the previous lap transition (first 5 seconds of the lap)
                if (_stopwatch.elapsed > const Duration(seconds: 5)) {
                  _stopTiming();
                } else {
                  print("Ignoring delayed OBS stop event from previous lap transition.");
                }
              }
            } else {
              if (_mediaRecorder == null || _mediaRecorder!.state != 'recording') {
                _startBrowserRecording();
              }
              if (!_isRunning) {
                _startTiming();
                _startStreaming();
              }
            }
          } else if (eventType == 'VirtualCamStateChanged') {
            setState(() {
              _vcamActive = eventData['outputActive'] ?? false;
            });
            if (_vcamActive) {
              _getAllCameras();
            }
          }
        }
      });

      _obsSocket!.onClose.listen((e) {
        setState(() {
          _obsConnected = false;
          _obsRecording = false;
        });
        print('OBS WebSocket closed. Retrying in 5s...');
        Future.delayed(const Duration(seconds: 5), () {
          if (mounted) _connectObs();
        });
      });

      _obsSocket!.onError.listen((e) {
        print('OBS WebSocket error (Split).');
      });
    } catch (e) {
      print('OBS connect exception (Split): $e');
    }
  }

  void _initAudioContext() {
    try {
      if (_audioContext == null) {
        final js.JsFunction ctxClass = (js.context['AudioContext'] ?? js.context['webkitAudioContext']) as js.JsFunction;
        _audioContext = js.JsObject(ctxClass);
      }
      if (_audioContext != null) {
        _audioContext!.callMethod('resume');
      }
    } catch (e) {
      print("Failed to initialize AudioContext: $e");
    }
  }

  void _playBeep({double frequency = 2000.0, double duration = 0.3}) {
    try {
      _initAudioContext();
      final js.JsObject? ctx = _audioContext;
      if (ctx == null) return;
      
      final js.JsObject osc = ctx.callMethod('createOscillator');
      final js.JsObject gain = ctx.callMethod('createGain');
      
      osc['type'] = 'sine';
      osc['frequency']['value'] = frequency;
      
      final double currentTime = ctx['currentTime'];
      gain['gain'].callMethod('setValueAtTime', [0.35, currentTime]);
      // Pierce, clean professional swimming pre-start countdown beep
      gain['gain'].callMethod('exponentialRampToValueAtTime', [0.0001, currentTime + duration]);
      
      osc.callMethod('connect', [gain]);
      gain.callMethod('connect', [ctx['destination']]);
      
      osc.callMethod('start');
      osc.callMethod('stop', [currentTime + duration]);
    } catch (e) {
      print("Audio play error: $e");
    }
  }

  void _playGunshot() {
    try {
      _initAudioContext();
      final js.JsObject? ctx = _audioContext;
      if (ctx == null) return;
      final double currentTime = ctx['currentTime'];
      final double sampleRate = ctx['sampleRate'].toDouble();

      // Create a 2.5-second buffer for the whistle
      final double duration = 2.5;
      final int bufferSize = (sampleRate * duration).toInt();
      final js.JsObject buffer = ctx.callMethod('createBuffer', [1, bufferSize, sampleRate]);
      final js.JsObject data = buffer.callMethod('getChannelData', [0]);
      
      final rand = math.Random(42);
      
      // Initialize states for bandpass filter
      final double noiseBandpassFreq = 2100.0;
      final double noiseBandpassQ = 1.5;
      final double w0 = 2.0 * math.pi * noiseBandpassFreq / sampleRate;
      final double alpha = math.sin(w0) / (2.0 * noiseBandpassQ);
      
      final double a0 = 1.0 + alpha;
      final double b0Norm = alpha / a0;
      final double b1Norm = 0.0;
      final double b2Norm = -alpha / a0;
      final double a1Norm = -2.0 * math.cos(w0) / a0;
      final double a2Norm = (1.0 - alpha) / a0;
      
      double x1 = 0.0, x2 = 0.0;
      double y1 = 0.0, y2 = 0.0;
      
      // Generate the raw white noise in an array
      final List<double> noise = List<double>.filled(bufferSize, 0.0);
      for (int i = 0; i < bufferSize; i++) {
        noise[i] = (rand.nextDouble() * 2.0 - 1.0) * 0.8;
      }
      
      // Filter the noise
      final List<double> filteredNoise = List<double>.filled(bufferSize, 0.0);
      for (int i = 0; i < bufferSize; i++) {
        final double x = noise[i];
        final double y = b0Norm * x + b1Norm * x1 + b2Norm * x2 - a1Norm * y1 - a2Norm * y2;
        filteredNoise[i] = y;
        x2 = x1;
        x1 = x;
        y2 = y1;
        y1 = y;
      }
      
      // Synthesize tones and mix
      double phase1 = 0.0;
      double phase2 = 0.0;
      
      final List<double> signal = List<double>.filled(bufferSize, 0.0);
      
      final double hornFreq = 2100.0;
      final double hornDur = 1.2;
      
      for (int i = 0; i < bufferSize; i++) {
        final double t = i / sampleRate;
        
        // 1) Pitch Sweep from 1700Hz to 2100Hz
        final double fSweep = hornFreq - 400.0 * math.exp(-t / 0.06);
        
        // 2) Vibrato and Tremolo (65Hz)
        final double vibrato = 120.0 * math.sin(2.0 * math.pi * 65.0 * t);
        final double tremolo = 0.65 + 0.35 * math.sin(2.0 * math.pi * 65.0 * t);
        
        // Double-tone
        final double f1 = fSweep + vibrato;
        final double f2 = (fSweep * 1.07) + vibrato;
        
        phase1 += 2.0 * math.pi * f1 / sampleRate;
        phase2 += 2.0 * math.pi * f2 / sampleRate;
        
        // 3) Mix tones with 3rd and 5th harmonics
        final double tone1 = math.sin(phase1) + 0.25 * math.sin(phase1 * 3.0) + 0.1 * math.sin(phase1 * 5.0);
        final double tone2 = math.sin(phase2) + 0.25 * math.sin(phase2 * 3.0) + 0.1 * math.sin(phase2 * 5.0);
        double whistleCore = (tone1 + tone2) * 0.5 * tremolo;
        
        // 4) Soft saturation (tanh)
        double mult = whistleCore * 2.2;
        if (mult > 10.0) mult = 10.0;
        if (mult < -10.0) mult = -10.0;
        final double expMult = math.exp(mult);
        final double expNegMult = math.exp(-mult);
        whistleCore = (expMult - expNegMult) / (expMult + expNegMult);
        
        // Air noise
        final double airNoise = filteredNoise[i] * 0.25;
        
        // 5) Envelope
        double envelope = 0.0;
        if (t < 0.06) {
          envelope = t / 0.06;
        } else if (t < 0.65) {
          envelope = 1.0;
        } else {
          envelope = math.exp(-(t - 0.65) / 0.25);
        }
        
        signal[i] = (whistleCore * 0.8 + airNoise * 0.2) * envelope * 0.95;
      }
      
      // Normalize to prevent distortion and maximize sound density
      double maxVal = 0.0;
      for (int i = 0; i < bufferSize; i++) {
        final double absVal = signal[i].abs();
        if (absVal > maxVal) {
          maxVal = absVal;
        }
      }
      
      if (maxVal > 0.0) {
        for (int i = 0; i < bufferSize; i++) {
          data[i] = signal[i] / maxVal;
        }
      }
      
      // Create Buffer Source and connect to destination
      final js.JsObject source = ctx.callMethod('createBufferSource');
      source['buffer'] = buffer;
      source.callMethod('connect', [ctx['destination']]);
      source.callMethod('start', [currentTime]);
    } catch (e) {
      print("Whistle synthesis error: $e");
      _playBeep(frequency: 2000.0, duration: 0.8); // Fallback long beep
    }
  }

  void _playStartSignalWav({double startTime = 0.0}) {
    try {
      _initAudioContext();
      _activeAudioElement?.pause();
      final audio = html.AudioElement('start_signal_test.wav');
      _activeAudioElement = audio;
      if (startTime > 0.0) {
        audio.onLoadedMetadata.listen((_) {
          audio.currentTime = startTime;
          audio.play();
        });
      } else {
        audio.play();
      }
    } catch (e) {
      print("Error playing start_signal_test.wav: $e");
      // Fallback to synthesis
      if (startTime >= 5.0) {
        _playGunshot();
      } else {
        _playBeep(frequency: 2000.0, duration: 0.3);
      }
    }
  }

  // --- Recording & Timer Control Logic ---
  void _startCountdownAndRecord() {
    _initAudioContext(); // Ensure AudioContext is fully unlocked on click!
    
    _activeAudioElement?.pause();
    final audio = html.AudioElement('start_signal_test.wav');
    _activeAudioElement = audio;

    setState(() {
      _countdownValue = 5;
      _isCountingDown = true;
    });

    try {
      audio.play();
    } catch (e) {
      print("Error calling audio.play(): $e");
    }

    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        if (_countdownValue > 1) {
          _countdownValue--;
          
          // Fallback synthesized beep if WAV audio is blocked/paused
          final bool isAudioPlaying = _activeAudioElement != null && !_activeAudioElement!.paused;
          if (!isAudioPlaying) {
            _playBeep(frequency: 2000.0, duration: 0.3);
          }
        } else {
          timer.cancel();
          _isCountingDown = false;
          
          // Fallback synthesized gunshot if WAV audio is blocked/paused
          final bool isAudioPlaying = _activeAudioElement != null && !_activeAudioElement!.paused;
          if (!isAudioPlaying) {
            _playGunshot();
          }
          _startObsRecording();
        }
      });
    });
  }

  void _cancelCountdown() {
    _countdownTimer?.cancel();
    _activeAudioElement?.pause();
    _activeAudioElement = null;
    setState(() {
      _isCountingDown = false;
      _countdownValue = 0;
    });
  }

  void _startObsRecording() {
    if (_obsConnected && _obsSocket != null) {
      try {
        _obsSocket!.sendString(jsonEncode({
          'op': 6,
          'd': {
            'requestType': 'StartRecord',
            'requestId': 'start_record_req'
          }
        }));
      } catch (e) {
        print('Error sending OBS start request: $e');
      }
    }

    setState(() {
      _obsRecording = true;
    });

    _startTiming();
    _startBrowserRecording();
    _startStreaming(); // Frame streaming starts only after recording starts!
  }

  void _stopObsRecording() {
    if (_obsConnected && _obsSocket != null) {
      try {
        _obsSocket!.sendString(jsonEncode({
          'op': 6,
          'd': {
            'requestType': 'StopRecord',
            'requestId': 'stop_record_req'
          }
        }));
      } catch (e) {
        print('Error sending OBS stop request: $e');
      }
    }

    if (_mediaRecorder != null && _mediaRecorder!.state == 'recording') {
      _mediaRecorder!.stop();
    }

    setState(() {
      _obsRecording = false;
    });

    _stopTiming();
  }

  void _startBrowserRecording() {
    if (_videoElement == null || _videoElement!.srcObject == null) return;

    try {
      _recordedChunks = [];
      final stream = _videoElement!.srcObject as html.MediaStream;
      final recordingLapNumber = _currentLapIndex + 1; // Capture exact lap number!

      String mimeType = 'video/webm;codecs=vp8,opus';
      if (!html.MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm';
      }

      _mediaRecorder = html.MediaRecorder(stream, {
        'mimeType': mimeType,
        'videoBitsPerSecond': 1200000, // 1.2 Mbps is identical to record_screen.dart
      });

      _mediaRecorder!.on['dataavailable'].listen((event) {
        final html.Blob? blob = (event as dynamic).data;
        if (blob != null && blob.size > 0) {
          _recordedChunks.add(blob);
        }
      });

      _mediaRecorder!.on['stop'].listen((event) {
        _uploadRecordedVideo(recordingLapNumber);
      });

      _mediaRecorder!.start();
      _recordingStartTime = DateTime.now();
      print('Browser recording started directly from MediaStream (No Canvas Overhead)');
    } catch (e) {
      print('Browser recording failed to start: $e');
    }
  }

  Future<void> _uploadRecordedVideo(int lapNumber) async {
    if (_recordingStartTime != null) {
      final duration = DateTime.now().difference(_recordingStartTime!);
      if (duration.inSeconds < 1) {
        print('Recording too short, skipping upload.');
        return;
      }
    }

    if (_recordedChunks.isEmpty) return;

    final blob = html.Blob(_recordedChunks, 'video/webm');

    // 1. Show the bottom-right notification for exactly 6 seconds!
    _bottomRightMessageTimer?.cancel();
    setState(() {
      _bottomRightMessage = "Lap $lapNumber影片錄製完成並上傳至平台!";
    });

    _bottomRightMessageTimer = Timer(const Duration(seconds: 6), () {
      if (mounted) {
        setState(() {
          _bottomRightMessage = null;
        });
      }
    });

    // 2. Perform background upload to the server (with skip_analysis=true so it skips visual analysis)
    try {
      final apiService = ApiService();
      final customFilename = 'lap_${lapNumber}_record_${DateTime.now().millisecondsSinceEpoch}.webm';
      apiService.uploadBlob(blob, skipAnalysis: true, customFilename: customFilename).then((videoId) {
        print("Background upload success for Lap $lapNumber. Video ID: $videoId");
      }).catchError((err) {
        print("Background upload failed for Lap $lapNumber: $err");
      });
    } catch (e) {
      print("Error initiating background upload: $e");
    }
  }

  // --- Split Stopwatch Timer Control ---
  // --- Split Stopwatch Timer Control ---
  void _startTiming() {
    setState(() {
      _laps = List.generate(_targetLaps, (i) => _LapState(lapNumber: i + 1));
      _currentLapIndex = 0;
      _lastWarningSecond = null;
      _isRunning = true;
      _lapStartTime = DateTime.now();
      _stopwatch.reset();
      _stopwatch.start();
      _lastTriggerState = false;
    });

    _stopwatchTimer?.cancel();
    _stopwatchTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
      if (!_isRunning) return;

      setState(() {
        final currentLap = _laps[_currentLapIndex];
        final now = DateTime.now();
        final elapsed = now.difference(_lapStartTime!);

        // 1. Update split time if not completed yet
        if (!currentLap.isCompleted) {
          currentLap.splitTime = _stopwatch.elapsed;
        }

        // 2. Handle remaining countdown
        final remaining = const Duration(minutes: 2) - elapsed;
        if (remaining <= Duration.zero) {
          currentLap.remainingTime = Duration.zero;
          
          // If the lap was never completed, trigger the finish naturally!
          if (!currentLap.isCompleted) {
            _onSwimmerCrossed();
          }

          // Advance to next lap or end session
          if (_currentLapIndex < _targetLaps - 1) {
            // If the audio element was not playing, we play the synthesized start signal (gunshot) fallback!
            final bool isAudioPlaying = _activeAudioElement != null && 
                !_activeAudioElement!.paused;
            if (!isAudioPlaying) {
              _playGunshot();
            }

            _currentLapIndex++;
            _laps[_currentLapIndex].isRunning = true;
            _lapStartTime = DateTime.now();
            _lastWarningSecond = null;
            _stopwatch.reset();
            _stopwatch.start();
            _lastTriggerState = false;
            _startBrowserRecording();
            _startStreaming();
            _obsRecording = true; // Toggle button back to Stop Recording!

            // CRITICAL FIX: Send StartRecord to OBS to start the next lap video recording!
            if (_obsConnected && _obsSocket != null) {
              try {
                _obsSocket!.sendString(jsonEncode({
                  'op': 6,
                  'd': {
                    'requestType': 'StartRecord',
                    'requestId': 'start_record_req'
                  }
                }));
                print("Sent StartRecord to OBS for Lap ${_currentLapIndex + 1}");
              } catch (e) {
                print('Error sending OBS start request for next lap: $e');
              }
            }
          } else {
            // Completed all laps!
            _stopTiming();
            _stopObsRecording();
          }
        } else {
          currentLap.remainingTime = remaining;

          // 3. Play warning beep in the last 5 seconds (uses wav or synthesized fallback)
          if (_currentLapIndex < _targetLaps - 1) {
            final remainingSeconds = remaining.inSeconds;
            if (remainingSeconds > 0 && remainingSeconds <= 5) {
              if (_lastWarningSecond != remainingSeconds) {
                _lastWarningSecond = remainingSeconds;
                if (remainingSeconds == 5) {
                  // Play the wav file from start (contains countdown beeps + gunshot)
                  _playStartSignalWav(startTime: 0.0);
                } else {
                  // Fallback synthesis if the wav audio was not successfully playing
                  final bool isAudioPlaying = _activeAudioElement != null && 
                      !_activeAudioElement!.paused;
                  if (!isAudioPlaying) {
                    _playBeep(frequency: 2000.0, duration: 0.3);
                  }
                }
              }
            }
          }
        }
      });
    });
  }

  void _stopTiming() {
    _stopwatch.stop();
    _stopwatchTimer?.cancel();
    _stopwatchTimer = null;
    _stopStreaming();
    setState(() {
      _isRunning = false;
      for (var lap in _laps) {
        lap.isRunning = false;
      }
    });
  }

  void _onSwimmerCrossed() {
    if (!_isRunning) return;

    // Prevent triggers in the first 15 seconds of the lap!
    if (_stopwatch.elapsed < const Duration(seconds: 15)) {
      print("Ignore swimmer trigger: Elapsed time (${_stopwatch.elapsed.inSeconds}s) is less than 15s.");
      return;
    }

    final currentLap = _laps[_currentLapIndex];
    if (currentLap.isCompleted) return; // Already triggered for this lap!

    // Freeze the split time!
    currentLap.splitTime = _stopwatch.elapsed;
    currentLap.isCompleted = true;

    // Immediately stop browser recording! (This triggers _uploadRecordedVideo() automatically!)
    if (_mediaRecorder != null && _mediaRecorder!.state == 'recording') {
      _mediaRecorder!.stop();
    }

    // Stop frame streaming to backend (so no more triggers occur for this lap)!
    _stopStreaming();

    // CRITICAL FIX: Send StopRecord command to OBS to save the current lap video!
    if (_obsConnected && _obsSocket != null) {
      try {
        _obsSocket!.sendString(jsonEncode({
          'op': 6,
          'd': {
            'requestType': 'StopRecord',
            'requestId': 'stop_record_req'
          }
        }));
        print("Sent StopRecord to OBS for Lap ${currentLap.lapNumber}");
      } catch (e) {
        print('Error sending OBS stop request inside _onSwimmerCrossed: $e');
      }
    }

    print("Swimmer crossed ROI for Lap ${currentLap.lapNumber}! Split time: ${currentLap.splitTime}");
    setState(() {
      _obsRecording = false;
    });

    // If it's the last lap, stop the timing session immediately!
    if (_currentLapIndex == _targetLaps - 1) {
      _stopTiming();
    }
  }

  void _sendConfigToBackend() {
    if (_realtimeSocket != null && _realtimeSocket!.readyState == html.WebSocket.OPEN) {
      final configMsg = jsonEncode({
        'action': 'update_config',
        'threshold': _detectorThreshold,
        'channel': _detectorChannel,
        'roi_x': _roiX,
        'roi_y': _roiY,
        'blue_var': _blueVar,
        'green_var': _greenVar,
        'red_var': _redVar,
        'is_locked': _isLocked,
        'locked_combo': _lockedCombo,
      });
      _realtimeSocket!.sendString(configMsg);
    }
  }

  void _showCalibrationDialog() {
    final TextEditingController threshCtrl = TextEditingController(text: _detectorThreshold.toStringAsFixed(1));

    setState(() {
      _isCalibrationOpen = true;
    });

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            _dialogSetState = setStateDialog;
            return Dialog(
              backgroundColor: Colors.grey[900],
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Container(
                width: 1100,
                padding: const EdgeInsets.all(24.0),
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: const [
                              Icon(Icons.tune, color: Colors.tealAccent, size: 22),
                              SizedBox(width: 8),
                              Text(
                                '校正畫面參數',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                          Positioned(
                            right: 0,
                            child: IconButton(
                              icon: const Icon(Icons.close, color: Colors.white70, size: 24),
                              onPressed: () => Navigator.of(context).pop(),
                            ),
                          )
                        ],
                      ),
                      const Divider(color: Colors.white24, height: 24),
                      
                      // 1. Threshold settings with manual text entry and -5 / +5 buttons
                      const Text(
                        '【偵測門檻值 (Threshold)】',
                        style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 18),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 10),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          ElevatedButton(
                            onPressed: () {
                              setStateDialog(() {
                                _detectorThreshold = (_detectorThreshold - 5).clamp(1.0, 100.0);
                                threshCtrl.text = _detectorThreshold.toStringAsFixed(1);
                              });
                              setState(() {
                                _detectorThreshold = _detectorThreshold;
                              });
                              _sendConfigToBackend();
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.grey[800],
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                            ),
                            child: const Text('-5', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 19)),
                          ),
                          const SizedBox(width: 16),
                          SizedBox(
                            width: 120,
                            child: TextField(
                              controller: threshCtrl,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: const InputDecoration(
                                contentPadding: EdgeInsets.symmetric(vertical: 12, horizontal: 12),
                                enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                                focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.tealAccent)),
                              ),
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 21),
                              textAlign: TextAlign.center,
                              onChanged: (val) {
                                final double? doubleValue = double.tryParse(val);
                                if (doubleValue != null) {
                                  setStateDialog(() {
                                    _detectorThreshold = doubleValue;
                                  });
                                  setState(() {
                                    _detectorThreshold = doubleValue;
                                  });
                                  _sendConfigToBackend();
                                }
                              },
                            ),
                          ),
                          const SizedBox(width: 16),
                          ElevatedButton(
                            onPressed: () {
                              setStateDialog(() {
                                _detectorThreshold = (_detectorThreshold + 5).clamp(1.0, 100.0);
                                threshCtrl.text = _detectorThreshold.toStringAsFixed(1);
                              });
                              setState(() {
                                _detectorThreshold = _detectorThreshold;
                              });
                              _sendConfigToBackend();
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.grey[800],
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                            ),
                            child: const Text('+5', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 19)),
                          ),
                        ],
                      ),
                      
                      const SizedBox(height: 24),

                      // 2. Lock dynamic formula
                      Column(
                        children: [
                          Text(
                            _isLocked ? '🔒 【已鎖定決策公式】' : '⚡ 【當前畫面最佳尋優公式 (動態追蹤中)】',
                            style: TextStyle(
                              color: _isLocked ? Colors.redAccent : Colors.orangeAccent, 
                              fontWeight: FontWeight.bold, 
                              fontSize: 18,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 12),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: _isLocked ? Colors.red.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: _isLocked ? Colors.redAccent.withOpacity(0.4) : Colors.orangeAccent.withOpacity(0.4),
                                width: 2,
                              ),
                            ),
                            child: Text(
                              "${(_blueVar == 0 ? '(B - Bref)' : '(Bref - B)')} + ${(_greenVar == 0 ? '(G - Gref)' : '(Gref - G)')} + ${(_redVar == 0 ? '(R - Rref)' : '(Rref - R)')}",
                              style: TextStyle(
                                color: _isLocked ? Colors.redAccent : Colors.orangeAccent,
                                fontSize: 24,
                                fontFamily: 'monospace',
                                fontWeight: FontWeight.bold,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton.icon(
                            onPressed: () {
                              setStateDialog(() {
                                _isLocked = !_isLocked;
                              });
                              setState(() {
                                _isLocked = _isLocked;
                              });
                              _sendConfigToBackend();
                            },
                            icon: Icon(_isLocked ? Icons.lock_open : Icons.lock, size: 22),
                            label: Text(
                              _isLocked ? '解鎖並恢復動態尋優' : '確定鎖定當前最佳公式',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _isLocked ? Colors.red[800] : Colors.green[800],
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 36, vertical: 16),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                            ),
                          ),
                          if (_isLocked) ...[
                            const SizedBox(height: 24),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                // Blue channel settings
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.center,
                                    children: [
                                      const Text(
                                        '【手動微調 Blue】',
                                        style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
                                        textAlign: TextAlign.center,
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _blueVar = 0; _lockedCombo[0] = 0; });
                                                setState(() { _blueVar = 0; _lockedCombo[0] = 0; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _blueVar == 0 ? Colors.blue[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('B-Bref(正)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _blueVar = 1; _lockedCombo[0] = 1; });
                                                setState(() { _blueVar = 1; _lockedCombo[0] = 1; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _blueVar == 1 ? Colors.blue[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('Bref-B(負)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 16),
                                // Green channel settings
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.center,
                                    children: [
                                      const Text(
                                        '【手動微調 Green】',
                                        style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
                                        textAlign: TextAlign.center,
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _greenVar = 0; _lockedCombo[1] = 0; });
                                                setState(() { _greenVar = 0; _lockedCombo[1] = 0; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _greenVar == 0 ? Colors.green[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('G-Gref(正)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _greenVar = 1; _lockedCombo[1] = 1; });
                                                setState(() { _greenVar = 1; _lockedCombo[1] = 1; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _greenVar == 1 ? Colors.green[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('Gref-G(負)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 16),
                                // Red channel settings
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.center,
                                    children: [
                                      const Text(
                                        '【手動微調 Red】',
                                        style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 16),
                                        textAlign: TextAlign.center,
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _redVar = 0; _lockedCombo[2] = 0; });
                                                setState(() { _redVar = 0; _lockedCombo[2] = 0; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _redVar == 0 ? Colors.red[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('R-Rref(正)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: ElevatedButton(
                                              onPressed: () {
                                                setStateDialog(() { _redVar = 1; _lockedCombo[2] = 1; });
                                                setState(() { _redVar = 1; _lockedCombo[2] = 1; });
                                                _sendConfigToBackend();
                                              },
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: _redVar == 1 ? Colors.red[800] : Colors.grey[800],
                                                foregroundColor: Colors.white,
                                                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
                                              ),
                                              child: const Text('Rref-R(負)', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),

                      const SizedBox(height: 24),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text(
                            '【即時訊號波形 (Raw RGB & Score)】',
                            style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 18),
                          ),
                          const SizedBox(width: 16),
                          ElevatedButton.icon(
                            onPressed: () {
                              if (_frameTimer != null) {
                                _stopStreaming();
                              } else {
                                _startStreaming();
                              }
                              setStateDialog(() {});
                            },
                            icon: Icon(
                              _frameTimer != null ? Icons.stop : Icons.videocam,
                              color: Colors.white,
                              size: 22,
                            ),
                            label: Text(
                              _frameTimer != null ? '停止觀測' : '開啟即時觀測',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _frameTimer != null ? Colors.red[700] : Colors.green[700],
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Container(
                        height: 520,
                        decoration: BoxDecoration(
                          color: Colors.black38,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.white12),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: CustomPaint(
                            painter: WaveformPainter(
                              rHistory: _chartRHistory,
                              gHistory: _chartGHistory,
                              bHistory: _chartBHistory,
                              scoreHistory: _chartScoreHistory,
                              threshold: _detectorThreshold,
                              refR: _refR,
                              refG: _refG,
                              refB: _refB,
                            ),
                            child: Container(),
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(),
                            child: const Text('關閉', style: TextStyle(color: Colors.tealAccent, fontSize: 21, fontWeight: FontWeight.bold)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    ).then((_) {
      _dialogSetState = null;
      setState(() {
        _isCalibrationOpen = false;
      });
    });
  }

  Future<void> _getAllCameras() async {
    try {
      try {
        final dummyStream = await html.window.navigator.mediaDevices!.getUserMedia({
          'video': true,
          'audio': false,
        });
        for (var track in dummyStream.getTracks()) {
          track.stop();
        }
      } catch (e) {
        print("Initial permission check warning: $e");
      }

      final devices = await html.window.navigator.mediaDevices?.enumerateDevices();
      _cameras = devices!.where((device) => device.kind == 'videoinput').cast<html.MediaDeviceInfo>().toList();

      if (_cameras.isNotEmpty) {
        int obsIndex = _cameras.indexWhere((c) => (c.label ?? '').toLowerCase().contains('obs'));
        if (obsIndex != -1) {
          bool success = await _initCamera(obsIndex);
          if (success) return;
        }

        bool anySuccess = false;
        for (int i = 0; i < _cameras.length; i++) {
          if (i == obsIndex) continue;
          anySuccess = await _initCamera(i);
          if (anySuccess) break;
        }

        if (!anySuccess) {
          print("No cameras could be initialized.");
        }
      } else {
        print("No cameras found.");
      }
    } catch (e) {
      print("Camera enumerate error: $e");
    }
  }

  Future<bool> _initCamera(int index) async {
    try {
      final camera = _cameras[index];

      final constraints = {
        'video': {
          'deviceId': camera.deviceId,
          'width': {'ideal': 3840},
          'height': {'ideal': 1080},
        },
        'audio': false,
      };

      final stream = await html.window.navigator.mediaDevices!.getUserMedia(constraints);

      _videoElement = html.VideoElement()
        ..srcObject = stream
        ..autoplay = true
        ..muted = true
        ..setAttribute('playsinline', 'true')
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.objectFit = 'fill';

      // Explicitly trigger play to prevent browser autoplay policy/decoding stalls!
      _videoElement!.play().catchError((err) {
        print("Explicit video play error: $err");
      });

      // ignore: undefined_prefixed_name
      ui.platformViewRegistry.registerViewFactory(
        _viewType,
        (int viewId) => _videoElement!,
      );

      if (mounted) {
        setState(() {
          _selectedCameraIndex = index;
          _isInit = true;
        });
      }
      return true;
    } catch (e) {
      print("Camera init error: $e");
      return false;
    }
  }

  void _switchCamera() async {
    if (_cameras.length < 2) return;

    _stopCamera();
    int newIndex = (_selectedCameraIndex + 1) % _cameras.length;

    setState(() {
      _isInit = false;
    });

    bool success = await _initCamera(newIndex);
    if (!success) {
      print("Failed to switch to camera $newIndex");
    }
  }

  void _stopCamera() {
    final stream = _videoElement?.srcObject as html.MediaStream?;
    if (stream != null) {
      for (var track in stream.getTracks()) {
        track.stop();
      }
    }
  }

  // --- Helper formatting methods ---
  String _formatTwoDigits(int n) {
    return n.toString().padLeft(2, '0');
  }

  String _formatDuration(Duration d) {
    final String minutes = _formatTwoDigits(d.inMinutes);
    final String seconds = _formatTwoDigits(d.inSeconds % 60);
    final String hundredths = _formatTwoDigits((d.inMilliseconds % 1000) ~/ 10);
    return '$minutes:$seconds.$hundredths';
  }

  // --- Widget Builders ---
  // --- Target Laps Dropdown Selector (Bottom-Left Float Card) ---
  Widget _buildTargetLapsSelector() {
    return Card(
      elevation: 4,
      color: Colors.black54,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.outlined_flag, color: Colors.white70, size: 24),
            const SizedBox(width: 10),
            const Text(
              'Target Laps (50m) : ',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(width: 6),
            DropdownButton<int>(
              value: _targetLaps,
              dropdownColor: Colors.black87,
              underline: const SizedBox(),
              style: const TextStyle(
                color: Colors.yellow,
                fontWeight: FontWeight.bold,
                fontSize: 20,
              ),
              items: [1, 2, 3, 4, 5, 6, 7, 8].map((int val) {
                return DropdownMenuItem<int>(
                  value: val,
                  child: Text('$val', style: const TextStyle(fontSize: 20)),
                );
              }).toList(),
              onChanged: _isRunning ? null : (int? newVal) {
                if (newVal != null) {
                  setState(() {
                    _targetLaps = newVal;
                    _hasSelectedLaps = true;
                    _laps = List.generate(_targetLaps, (i) => _LapState(lapNumber: i + 1));
                  });
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimingTableCard() {
    if (!_hasSelectedLaps) return const SizedBox();

    return Card(
      elevation: 4,
      color: Colors.grey[50],
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: 380,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Table Header Row
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2.0),
              child: Row(
                children: const [
                  Expanded(
                    flex: 2,
                    child: Text(
                      'Lap',
                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black, fontSize: 16),
                    ),
                  ),
                  Expanded(
                    flex: 3,
                    child: Text(
                      '計時時間',
                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black, fontSize: 16),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  Expanded(
                    flex: 3,
                    child: Text(
                      '剩餘時間',
                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black, fontSize: 16),
                      textAlign: TextAlign.right,
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 4),

            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _targetLaps,
              itemBuilder: (context, index) {
                final int lapNum = index + 1;
                
                final bool activeOrPast = _isRunning && index <= _currentLapIndex;
                final bool isCurrent = _isRunning && index == _currentLapIndex;
                
                String timeText = '--:--.--';
                String remainingText = index == _targetLaps - 1 ? '--:--.--' : '02:00.00';
                Color textColor = Colors.grey[400]!;
                
                if (_laps.isNotEmpty && index < _laps.length) {
                  final lap = _laps[index];
                  textColor = isCurrent ? Colors.deepOrange[700]! : (lap.isCompleted ? Colors.black87 : Colors.grey[400]!);
                  if (lap.splitTime != null) {
                    timeText = _formatDuration(lap.splitTime!);
                  }
                  if (index == _targetLaps - 1) {
                    remainingText = '--:--.--';
                  } else {
                    remainingText = _formatDuration(lap.remainingTime);
                  }
                }

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3.0),
                  child: Row(
                    children: [
                      // Column 1: Lap
                      Expanded(
                        flex: 2,
                        child: Text(
                          'Lap $lapNum',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: textColor,
                          ),
                        ),
                      ),
                      // Column 2: 計時時間
                      Expanded(
                        flex: 3,
                        child: Center(
                          child: Text(
                            timeText,
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: textColor,
                              fontFamily: 'Outfit',
                            ),
                          ),
                        ),
                      ),
                      // Column 3: 剩餘時間
                      Expanded(
                        flex: 3,
                        child: Text(
                          remainingText,
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: isCurrent ? Colors.red : textColor,
                            fontFamily: 'Outfit',
                          ),
                          textAlign: TextAlign.right,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRestCountdownOverlay() {
    if (!_isRunning || _laps.isEmpty || _currentLapIndex >= _laps.length) {
      return const SizedBox();
    }

    final lap = _laps[_currentLapIndex];
    if (!lap.isCompleted) {
      return const SizedBox();
    }

    final remaining = lap.remainingTime;
    final String minutes = _formatTwoDigits(remaining.inMinutes);
    final String seconds = _formatTwoDigits(remaining.inSeconds % 60);
    final String hundredths = _formatTwoDigits((remaining.inMilliseconds % 1000) ~/ 10);

    return Container(
      width: 300.0, // 固定寬度，完全防止數字跳動時看板左右閃爍
      alignment: Alignment.center, // 內容居中對齊
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.85),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.cyanAccent.withOpacity(0.5),
          width: 2.0,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.cyanAccent.withOpacity(0.2),
            blurRadius: 12,
            offset: const Offset(0, 4),
          )
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const Text(
                '休息剩餘時間',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  color: Colors.cyanAccent,
                  fontFamily: 'Outfit',
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '$minutes:$seconds.$hundredths',
                style: const TextStyle(
                  fontSize: 48,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  fontFamily: 'Outfit',
                  fontFeatures: [FontFeature.tabularFigures()],
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStopwatchTimerOverlay() {
    if (!_hasSelectedLaps) return const SizedBox();

    Duration elapsed = _stopwatch.elapsed;
    if (_laps.isNotEmpty && _currentLapIndex < _laps.length) {
      final lap = _laps[_currentLapIndex];
      if (lap.isCompleted && lap.splitTime != null) {
        elapsed = lap.splitTime!;
      }
    }

    final String minutes = _formatTwoDigits(elapsed.inMinutes);
    final String seconds = _formatTwoDigits(elapsed.inSeconds % 60);
    final String hundredths = _formatTwoDigits((elapsed.inMilliseconds % 1000) ~/ 10);

    final int displayLap = _currentLapIndex + 1;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.75),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.white24,
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 10,
            offset: const Offset(0, 4),
          )
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            'Lap $displayLap  ',
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.yellowAccent,
              fontFamily: 'Outfit',
            ),
          ),
          Text(
            '$minutes:$seconds.$hundredths',
            style: const TextStyle(
              fontSize: 48,
              fontWeight: FontWeight.bold,
              color: Colors.white,
              fontFamily: 'Outfit',
              fontFeatures: [FontFeature.tabularFigures()],
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlBar() {
    final bool isObsConnected = _obsConnected;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Colors.black54,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            isObsConnected ? 'OBS Ready' : 'OBS Disconnected',
            style: TextStyle(
              color: isObsConnected ? Colors.white : Colors.redAccent,
              fontWeight: FontWeight.bold,
              fontSize: 20,
            ),
          ),
          const SizedBox(width: 24),
          if (isObsConnected) ...[
            if (!_obsRecording)
              if (_isCountingDown)
                ElevatedButton.icon(
                  onPressed: _cancelCountdown,
                  icon: const Icon(Icons.cancel, color: Colors.white, size: 24),
                  label: Text(
                    'Cancel ($_countdownValue)',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange[700],
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  ),
                )
              else
                ElevatedButton.icon(
                  onPressed: _startCountdownAndRecord,
                  icon: const Icon(Icons.radio_button_checked, color: Colors.white, size: 24),
                  label: const Text(
                    'Start Recording',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green[600],
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  ),
                )
            else
              ElevatedButton.icon(
                onPressed: _stopObsRecording,
                icon: const Icon(Icons.stop, color: Colors.white, size: 24),
                label: const Text(
                  'Stop Recording',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red[700],
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                ),
              ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);

    if (_cameras.isEmpty) {
      return const Center(
        child: Text('No cameras found. Please check permissions.'),
      );
    }

    final bool showCountdownOverlay = _isCountingDown ||
        (_isRunning &&
         _laps.isNotEmpty &&
         _currentLapIndex < _laps.length &&
         _currentLapIndex < _targetLaps - 1 &&
         _laps[_currentLapIndex].remainingTime.inSeconds > 0 &&
         _laps[_currentLapIndex].remainingTime.inSeconds <= 5);

    final String countdownText = _isCountingDown
        ? '$_countdownValue'
        : (_laps.isNotEmpty && _currentLapIndex < _laps.length
            ? '${_laps[_currentLapIndex].remainingTime.inSeconds}'
            : '0');

    return Scaffold(
      backgroundColor: Colors.white, // Pure white background
      body: Stack(
        children: [


          // 2. Centered AspectRatio Container to preserve original 32:9 ratio perfectly
          if (_isInit)
            Center(
              child: AspectRatio(
                aspectRatio: 3840.0 / 1080.0,
                child: Stack(
                  children: [
                    HtmlElementView(
                      key: const ValueKey('cameraVideo_split_view_key'),
                      viewType: _viewType,
                    ),
                    if (_isCalibrationOpen)
                      Positioned.fill(
                        child: IgnorePointer(
                          child: CustomPaint(
                            painter: RoiPainter(
                              inCooldown: _inCooldown,
                              activeScore: _detectorScore,
                              roiX: _roiX,
                              roiY: _roiY,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            )
          else
            const Center(child: CircularProgressIndicator()),

          // 3. Timing Table positioned Float in Top-Right
          Positioned(
            top: 20,
            right: 40,
            child: _buildTimingTableCard(),
          ),

          // Target Laps Selector positioned Float in Bottom-Left
          Positioned(
            bottom: 20,
            left: 30,
            child: _buildTargetLapsSelector(),
          ),

          // 4. Stopwatch Overlay centered in top-center of the screen
          Positioned(
            top: 75,
            left: 0,
            right: 0,
            child: Center(
              child: _buildStopwatchTimerOverlay(),
            ),
          ),

          // 4.5 Rest Countdown Overlay in the middle between center stopwatch and top-right table
          Positioned(
            top: 75,
            right: 480, // Sits beautifully in the center-right empty space!
            child: _buildRestCountdownOverlay(),
          ),

          // 5. OBS Control Bar
          Positioned(
            bottom: 30,
            left: 0,
            right: 0,
            child: Center(
              child: _buildControlBar(),
            ),
          ),

          // 6. Calibration & Camera Controls
          Positioned(
            bottom: 20,
            right: 30,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_hasSelectedLaps) ...[
                  ElevatedButton(
                    onPressed: _showCalibrationDialog,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.grey[700],
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      elevation: 6,
                    ),
                    child: const Text(
                      'Calibration',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
                if (_cameras.length > 1) ...[
                  FloatingActionButton(
                    heroTag: 'refreshCamSplit',
                    onPressed: () {
                      _getAllCameras();
                      if (_obsConnected) {
                        _obsSocket!.sendString(jsonEncode({
                          'op': 6,
                          'd': {
                            'requestType': 'GetVirtualCamStatus',
                            'requestId': 'get_vcam'
                          }
                        }));
                      }
                    },
                    child: const Icon(Icons.refresh),
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black,
                    mini: true,
                  ),
                  const SizedBox(width: 8),
                  FloatingActionButton(
                    heroTag: 'cameraSwitcherSplit',
                    onPressed: _switchCamera,
                    child: const Icon(Icons.cameraswitch),
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black,
                    mini: true,
                  ),
                ],
              ],
            ),
          ),

          // 7. Auto-Uploading Overlay
          if (_isAutoUploading)
            Container(
              color: Colors.black54,
              child: Center(
                child: Card(
                  elevation: 8,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 30),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 24),
                        Text(
                          _completionStatus ?? '處理中...',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),

          // 8. Large Countdown Overlay
          if (showCountdownOverlay)
            Container(
              color: Colors.black45,
              child: Center(
                child: Text(
                  countdownText,
                  style: const TextStyle(
                    fontSize: 250,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    shadows: [
                      Shadow(color: Colors.black, blurRadius: 15)
                    ],
                  ),
                ),
              ),
            ),
          
          // 9. Floating Bottom-Right Notification Toast/Card
          if (_bottomRightMessage != null)
            Positioned(
              bottom: 25,
              right: 30,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                  border: Border.all(color: Colors.greenAccent.withOpacity(0.5), width: 1.5),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle, color: Colors.white, size: 30),
                    const SizedBox(width: 14),
                    Text(
                      _bottomRightMessage!,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// CustomPainter to draw only the Secondary ROI overlaying the 32:9 view
class RoiPainter extends CustomPainter {
  final bool inCooldown;
  final double activeScore;
  final List<int> roiX;
  final List<int> roiY;

  RoiPainter({
    required this.inCooldown,
    required this.activeScore,
    required this.roiX,
    required this.roiY,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Map coordinates from native 3840x1080 to actual widget size
    final double scaleX = size.width / 3840.0;
    final double scaleY = size.height / 1080.0;

    // Use dynamic ROI coordinates
    final double secX1 = roiX[0] * scaleX;
    final double secX2 = roiX[1] * scaleX;
    final double secY1 = roiY[0] * scaleY;
    final double secY2 = roiY[1] * scaleY;

    final rectSec = Rect.fromLTRB(secX1, secY1, secX2, secY2);
    final paintSec = Paint()
      ..color = Colors.orange.withOpacity(0.9)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0;

    // Draw rectangle
    canvas.drawRect(rectSec, paintSec);

    // Draw Label with Real-time Diff Score
    final textPainterSec = TextPainter(
      text: TextSpan(
        text: 'Detection ROI (${roiX[0]}-${roiX[1]}, ${roiY[0]}-${roiY[1]})\nDiff: ${activeScore.toStringAsFixed(1)}',
        style: TextStyle(
          color: Colors.orange[100],
          fontSize: 11,
          fontWeight: FontWeight.bold,
          backgroundColor: Colors.black54,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainterSec.layout();
    textPainterSec.paint(canvas, Offset(secX1, secY1 - 28));
  }

  @override
  bool shouldRepaint(covariant RoiPainter oldDelegate) {
    return oldDelegate.inCooldown != inCooldown ||
        oldDelegate.activeScore != activeScore ||
        oldDelegate.roiX[0] != roiX[0] ||
        oldDelegate.roiX[1] != roiX[1] ||
        oldDelegate.roiY[0] != roiY[0] ||
        oldDelegate.roiY[1] != roiY[1];
  }
}

// CustomPainter to draw scrolling 4-channel real-time waveforms (R, G, B raw, and Decision Score)
class WaveformPainter extends CustomPainter {
  final List<double> rHistory;
  final List<double> gHistory;
  final List<double> bHistory;
  final List<double> scoreHistory;
  final double threshold;
  final double refR;
  final double refG;
  final double refB;

  WaveformPainter({
    required this.rHistory,
    required this.gHistory,
    required this.bHistory,
    required this.scoreHistory,
    required this.threshold,
    required this.refR,
    required this.refG,
    required this.refB,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final double subplotHeight = size.height / 4;
    final int maxPoints = 150;
    final double leftMargin = 45.0;
    final double rightMargin = 55.0;
    final double plotWidth = size.width - leftMargin - rightMargin;

    // Helper to draw a single channel plot
    void drawSubplot(List<double> data, Color color, String title, int index, double minVal, double maxVal, {double? thresh, double? baseline}) {
      final double top = index * subplotHeight;
      final double bottom = top + subplotHeight;
      
      // Draw grid/background
      final bgPaint = Paint()..color = Colors.black26;
      canvas.drawRect(Rect.fromLTRB(leftMargin, top + 2, size.width - rightMargin, bottom - 2), bgPaint);

      // Draw border around the chart area
      final borderPaint = Paint()
        ..color = Colors.white10
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0;
      canvas.drawRect(Rect.fromLTRB(leftMargin, top, size.width - rightMargin, bottom), borderPaint);

      // Draw middle grid line
      final gridPaint = Paint()
        ..color = Colors.white.withOpacity(0.04)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0;
      canvas.drawLine(
        Offset(leftMargin, top + subplotHeight / 2),
        Offset(size.width - rightMargin, top + subplotHeight / 2),
        gridPaint,
      );

      // Draw title text
      final textPainter = TextPainter(
        text: TextSpan(
          text: title,
          style: const TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold),
        ),
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(canvas, Offset(leftMargin + 8, top + 4));

      // Draw Y-axis Max Label on the left
      final maxPainter = TextPainter(
        text: TextSpan(
          text: maxVal.toStringAsFixed(0),
          style: const TextStyle(color: Colors.white54, fontSize: 11.5, fontWeight: FontWeight.bold),
        ),
        textDirection: TextDirection.ltr,
      );
      maxPainter.layout();
      maxPainter.paint(canvas, Offset(4, top + 4));

      // Draw Y-axis Min Label on the left
      final minPainter = TextPainter(
        text: TextSpan(
          text: minVal.toStringAsFixed(0),
          style: const TextStyle(color: Colors.white54, fontSize: 11.5, fontWeight: FontWeight.bold),
        ),
        textDirection: TextDirection.ltr,
      );
      minPainter.layout();
      minPainter.paint(canvas, Offset(4, bottom - 14));

      // Draw Y-axis Mid Label on the left
      final midVal = minVal + (maxVal - minVal) / 2;
      final midPainter = TextPainter(
        text: TextSpan(
          text: midVal.toStringAsFixed(0),
          style: const TextStyle(color: Colors.white30, fontSize: 11.5),
        ),
        textDirection: TextDirection.ltr,
      );
      midPainter.layout();
      midPainter.paint(canvas, Offset(4, top + (subplotHeight / 2) - 6));

      // Draw current value text on the right
      if (data.isNotEmpty) {
        final valPainter = TextPainter(
          text: TextSpan(
            text: data.last.toStringAsFixed(1),
            style: TextStyle(color: color, fontSize: 13.5, fontWeight: FontWeight.bold),
          ),
          textDirection: TextDirection.ltr,
        );
        valPainter.layout();
        valPainter.paint(canvas, Offset(size.width - rightMargin + 6, top + subplotHeight / 2 - 8));
      }

      if (data.length < 2) return;

      // Draw Line path
      final path = Path();
      final double range = (maxVal - minVal) == 0 ? 1.0 : (maxVal - minVal);
      final double dx = plotWidth / (maxPoints - 1);

      for (int i = 0; i < data.length; i++) {
        final double x = leftMargin + i * dx;
        final double normalized = (data[i] - minVal) / range;
        final double clamped = normalized.clamp(0.0, 1.0);
        final double y = bottom - 4 - clamped * (subplotHeight - 16);

        if (i == 0) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
      }

      final linePaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;
      canvas.drawPath(path, linePaint);

      // Draw Baseline line if specified (dotted)
      if (baseline != null && baseline > 0) {
        final double normalizedBase = (baseline - minVal) / range;
        final double clampedBase = normalizedBase.clamp(0.0, 1.0);
        final double baseY = bottom - 4 - clampedBase * (subplotHeight - 16);

        final basePaint = Paint()
          ..color = color.withOpacity(0.55)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0;
        
        double startX = leftMargin;
        while (startX < size.width - rightMargin) {
          canvas.drawLine(Offset(startX, baseY), Offset(startX + 3, baseY), basePaint);
          startX += 7;
        }

        // Draw baseline label value text
        final baseLabelPainter = TextPainter(
          text: TextSpan(
            text: 'Ref:${baseline.toStringAsFixed(1)}',
            style: TextStyle(color: color.withOpacity(0.85), fontSize: 11.5, fontWeight: FontWeight.bold),
          ),
          textDirection: TextDirection.ltr,
        );
        baseLabelPainter.layout();
        baseLabelPainter.paint(canvas, Offset(size.width - rightMargin - 85, baseY - 14));
      }

      // Draw Threshold line if specified (dashed)
      if (thresh != null) {
        final double normalizedThresh = (thresh - minVal) / range;
        final double clampedThresh = normalizedThresh.clamp(0.0, 1.0);
        final double threshY = bottom - 4 - clampedThresh * (subplotHeight - 16);

        final threshPaint = Paint()
          ..color = Colors.redAccent.withOpacity(0.9)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0;
        
        double startX = leftMargin;
        while (startX < size.width - rightMargin) {
          canvas.drawLine(Offset(startX, threshY), Offset(startX + 4, threshY), threshPaint);
          startX += 8;
        }

        // Draw threshold label value text
        final threshLabelPainter = TextPainter(
          text: TextSpan(
            text: 'Th:${thresh.toStringAsFixed(1)}',
            style: const TextStyle(color: Colors.redAccent, fontSize: 11.5, fontWeight: FontWeight.bold),
          ),
          textDirection: TextDirection.ltr,
        );
        threshLabelPainter.layout();
        threshLabelPainter.paint(canvas, Offset(size.width - rightMargin - 85, threshY - 14));
      }
    }

    // Helper to calculate dynamic min/max with span of at least 100 centered around reference
    Map<String, double> getDynamicBounds(List<double> history, double ref) {
      double minVal = ref - 50;
      double maxVal = ref + 50;
      for (var val in history) {
        if (val < minVal) minVal = val - 10;
        if (val > maxVal) maxVal = val + 10;
      }
      if (maxVal - minVal < 100) {
        double center = (maxVal + minVal) / 2;
        minVal = center - 50;
        maxVal = center + 50;
      }
      if (minVal < 0) {
        minVal = 0;
        maxVal = 100;
      }
      if (maxVal > 255) {
        maxVal = 255;
        minVal = 155;
      }
      return {'min': minVal, 'max': maxVal};
    }

    final boundsR = getDynamicBounds(rHistory, refR);
    final boundsG = getDynamicBounds(gHistory, refG);
    final boundsB = getDynamicBounds(bHistory, refB);

    // 1. Red channel: dynamic range (span ~100)
    drawSubplot(rHistory, Colors.redAccent, 'Red Channel', 0, boundsR['min']!, boundsR['max']!, baseline: refR);

    // 2. Green channel: dynamic range (span ~100)
    drawSubplot(gHistory, Colors.greenAccent, 'Green Channel', 1, boundsG['min']!, boundsG['max']!, baseline: refG);

    // 3. Blue channel: dynamic range (span ~100)
    drawSubplot(bHistory, Colors.blueAccent, 'Blue Channel', 2, boundsB['min']!, boundsB['max']!, baseline: refB);

    // 4. Decision Score: min=-50, max=100 (composite can be negative because of Mode)
    double maxScore = threshold * 2;
    if (maxScore < 20) maxScore = 20;
    double minScore = -30;
    for (var s in scoreHistory) {
      if (s > maxScore) maxScore = s + 5.0;
      if (s < minScore) minScore = s - 5.0;
    }
    drawSubplot(scoreHistory, Colors.orangeAccent, 'Composite Score', 3, minScore, maxScore, thresh: threshold);
  }

  @override
  bool shouldRepaint(covariant WaveformPainter oldDelegate) {
    return oldDelegate.rHistory.length != rHistory.length ||
        (rHistory.isNotEmpty && oldDelegate.rHistory.isNotEmpty && oldDelegate.rHistory.last != rHistory.last) ||
        oldDelegate.threshold != threshold ||
        oldDelegate.refR != refR ||
        oldDelegate.refG != refG ||
        oldDelegate.refB != refB;
  }
}
