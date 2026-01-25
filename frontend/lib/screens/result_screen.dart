import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models.dart';
import '../api_service.dart';
import 'chart_widget.dart';

class ResultScreen extends StatefulWidget {
  final FullAnalysisResult result;

  const ResultScreen({Key? key, required this.result}) : super(key: key);

  @override
  _ResultScreenState createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  final ApiService _apiService = ApiService();
  VideoPlayerController? _videoPlayerController;
  ChewieController? _chewieController;
  bool _isVideoInitialized = false;
  final ValueNotifier<double> _currentTimeNotifier = ValueNotifier(0.0); // Notifier for Chart Sync

  // Focus Video State
  VideoPlayerController? _focusVideoController;
  bool _isFocusInitialized = false;
  bool _showFocusPiP = false;

  @override
  void initState() {
    super.initState();
    _initVideo();
  }

  Future<void> _initVideo() async {
    final videoUrl = _apiService.getDownloadUrl(widget.result.videoId);
    _videoPlayerController = VideoPlayerController.networkUrl(Uri.parse(videoUrl));

    try {
      await _videoPlayerController!.initialize();
      
      // Initialize Focus Video if available
      if (widget.result.focusCropVideoPath != null && widget.result.focusCropVideoPath!.isNotEmpty) {
         try {
           final focusUrl = _apiService.getDownloadUrl(widget.result.videoId, type: 'focus');
           _focusVideoController = VideoPlayerController.networkUrl(Uri.parse(focusUrl));
           await _focusVideoController!.initialize();
           await _focusVideoController!.setVolume(0); // Mute focus video
           _isFocusInitialized = true;
           print("Focus video initialized");
         } catch (e) {
           print("Focus video init error: $e");
         }
      }

      // Add Listener for Chart Synchronization & Focus Video Sync
      _videoPlayerController!.addListener(() {
         // 1. Chart Sync
         if (_videoPlayerController!.value.isPlaying) {
             _currentTimeNotifier.value = _videoPlayerController!.value.position.inMilliseconds / 1000.0;
         }
         
         // 2. Focus Video Sync
         if (_isFocusInitialized && _focusVideoController != null) {
            final mainValue = _videoPlayerController!.value;
            final focusValue = _focusVideoController!.value;
            
            // Sync Play/Pause
            if (mainValue.isPlaying != focusValue.isPlaying) {
                if (mainValue.isPlaying) _focusVideoController!.play();
                else _focusVideoController!.pause();
            }
            
            // Sync Position (Drift correction > 200ms)
            // Only sync if pip is showing (optimization) or always? Always is safer for ready-state.
            final drift = (mainValue.position - focusValue.position).inMilliseconds.abs();
            if (drift > 200) {
               _focusVideoController!.seekTo(mainValue.position);
            }
         }
      });

      _chewieController = ChewieController(
        videoPlayerController: _videoPlayerController!,
        autoPlay: true,
        looping: true,
        aspectRatio: _videoPlayerController!.value.aspectRatio,
        errorBuilder: (context, errorMessage) {
          return Center(
            child: Text(errorMessage, style: TextStyle(color: Colors.white)),
          );
        },
      );

      if (mounted) setState(() => _isVideoInitialized = true);
    } catch (e) {
      print("Video init error: $e");
    }
  }

  @override
  void dispose() {
    _stopLooping(); // Ensure listener is removed
    _currentTimeNotifier.dispose(); // Dispose notifier
    _videoPlayerController?.dispose();
    _chewieController?.dispose();
    _focusVideoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.result;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Custom Header (Not pinned, scrolls with content)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 16.0),
                child: Row(
                  children: [
                    IconButton(
                      icon: Icon(Icons.arrow_back),
                      onPressed: () => Navigator.of(context).pop(),
                    ),
                    Expanded(
                      child: Center(
                        child: Text(
                          'Analysis Dashboard',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                    ),
                    IconButton(
                      icon: Icon(Icons.download),
                      onPressed: () => launchUrl(Uri.parse(_apiService.getDownloadUrl(result.videoId))),
                      tooltip: 'Download Video',
                    ),
                  ],
                ),
              ),

              // 1. Metrics Section (Displayed TOP of video)
              Container(
                color: Colors.white,
                padding: const EdgeInsets.all(16.0),
                child: _buildHeaderMetrics(result),
              ),

              Divider(height: 1),

              // 2. Video Player Section
              Container(
                height: 400,
                width: double.infinity,
                color: Colors.black,
                child: _isVideoInitialized
                    ? ClipRect(
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            // 1. Scaled Video (Cover)
                            SizedBox.expand(
                              child: FittedBox(
                                fit: BoxFit.cover,
                                child: SizedBox(
                                  width: _videoPlayerController!.value.size.width,
                                  height: _videoPlayerController!.value.size.height,
                                  child: Chewie(controller: _chewieController!),
                                ),
                              ),
                            ),
                          
                            // PiP Focus Window
                          if (_showFocusPiP && _isFocusInitialized && _focusVideoController!.value.isInitialized)
                            Positioned(
                              top: 10,
                              right: 10,
                              width: _focusVideoController!.value.size.width * 1.3,
                              height: _focusVideoController!.value.size.height * 1.3,
                              child: GestureDetector(
                                onTap: () {
                                  setState(() {
                                    _showFocusPiP = false;
                                  });
                                },
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: Colors.black,
                                    border: Border.all(color: Colors.white, width: 2),
                                    boxShadow: [BoxShadow(blurRadius: 5, color: Colors.black54)]
                                  ),
                                  child: Stack(
                                    children: [
                                      VideoPlayer(_focusVideoController!),
                                      Positioned(
                                        top: 2, right: 2,
                                        child: Icon(Icons.close, color: Colors.white, size: 16)
                                      )
                                    ],
                                  ),
                                ),
                              ),
                            ),

                            // Toggle Button
                            if (_isFocusInitialized && !_showFocusPiP)
                              Positioned(
                                top: 10,
                                right: 10,
                                child: Tooltip(
                                  message: "Show Focus View",
                                  child: FloatingActionButton.small(
                                    backgroundColor: Colors.white.withOpacity(0.8),
                                    child: Icon(Icons.center_focus_strong, color: Colors.blueAccent),
                                    onPressed: () {
                                      setState(() {
                                        _showFocusPiP = true;
                                      });
                                    },
                                  ),
                                ),
                              ),
                          ],
                        ),
                      )
                    : Center(child: CircularProgressIndicator(color: Colors.white)),
              ),

              // 3. Charts/Waveforms Section (Displayed BELOW video) with Tabs
              if ((result.strokePlotFigs?.isNotEmpty ?? false) || (result.divingPlotFigs?.isNotEmpty ?? false))
                _buildChartTabs(context, result)
              else
                 Padding(
                   padding: EdgeInsets.all(16),
                   child: Text('No waveform data available for this analysis.'),
                 ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildChartTabs(BuildContext context, FullAnalysisResult result) {
    List<_ChartTabItem> tabs = [];

    // Helper to parse and add tabs
    void addTab(String key, InteractivePlot plot, bool isKickAngle) {
      int lapIndex = 999;
      String typeStr = isKickAngle ? "Kick Angle" : "Unknown";
      int typeOrder = 0; // 0: Kick, 1: Shoulder, 2: Wrist, 3: Other

      // 1. Determine Type
      if (isKickAngle) {
        typeStr = "Kick Angle";
        typeOrder = 0;
      } else {
        if (key.toLowerCase().contains("shoulder")) {
          typeStr = "Shoulder";
          typeOrder = 1;
        } else if (key.toLowerCase().contains("wrist")) {
          typeStr = "Wrist";
          typeOrder = 2;
        } else {
          typeStr = "Info"; // Fallback
          typeOrder = 3;
        }
      }

      // 2. Determine Lap Index
      final lapMatch = RegExp(r"lap(\d+)").firstMatch(key);
      if (lapMatch != null) {
        lapIndex = int.parse(lapMatch.group(1)!);
      } else {
        // Legacy support
        if (key.contains("range1") || key.contains("decreasing")) lapIndex = -2; // Treat as first
        else if (key.contains("range2") || key.contains("increasing")) lapIndex = -1; // Treat as second
      }
      
      tabs.add(_ChartTabItem(
        originalKey: key,
        plot: plot,
        realLapIndex: lapIndex,
        subType: typeStr,
        typeOrder: typeOrder,
        isKickAngle: isKickAngle
      ));
    }

    // Process Stroke Plots
    result.strokePlotFigs?.forEach((key, value) {
      addTab(key, value, false);
    });

    // Process Diving Plots
    result.divingPlotFigs?.forEach((key, value) {
      addTab(key, value, true);
    });

    if (tabs.isEmpty) return SizedBox.shrink();

    // 3. Normalize Lap Indices (Map sorted real indices to 1, 2, 3...)
    final uniqueIndices = tabs.map((e) => e.realLapIndex).toSet().toList()..sort();
    final Map<int, int> indexMap = {};
    for (int i = 0; i < uniqueIndices.length; i++) {
        indexMap[uniqueIndices[i]] = i + 1;
    }

    // 4. Update Labels & Sort
    for (var tab in tabs) {
      int displayIdx = indexMap[tab.realLapIndex]!;
      tab.displayLabel = "Lap $displayIdx ${tab.subType}";
    }

    // Sort: Lap ASC -> TypeOrder ASC
    tabs.sort((a, b) {
      int cmp = indexMap[a.realLapIndex]!.compareTo(indexMap[b.realLapIndex]!);
      if (cmp != 0) return cmp;
      return a.typeOrder.compareTo(b.typeOrder);
    });

    // Debug
    print("DEBUG: Generated Tabs: ${tabs.map((e) => e.displayLabel).toList()}");

    return DefaultTabController(
      length: tabs.length,
      child: Column(
        children: [
          Container(
            color: Colors.grey[100],
            child: TabBar(
              isScrollable: true,
              labelColor: Colors.blueAccent,
              unselectedLabelColor: Colors.grey,
              indicatorColor: Colors.blueAccent,
              tabs: tabs.map((t) => Tab(text: t.displayLabel)).toList(),
            ),
          ),
          Container(
            height: 500,
            padding: EdgeInsets.all(16),
            child: TabBarView(
              children: tabs.map((t) {
                return AnalysisChartWidget(
                  plotData: t.plot, 
                  lineColor: t.isKickAngle ? Colors.orangeAccent : Colors.blueAccent,
                  onPhaseTap: (start, end) => _handlePhaseReplay(start, end),
                  currentTimeNotifier: _currentTimeNotifier,
                );
              }).toList(),
            ),
          ),
          
          SizedBox(height: 16),
          Center(
            child: ElevatedButton.icon(
              onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
              icon: Icon(Icons.replay),
              label: Text('Analyze New Video'),
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              ),
            ),
          ),
          SizedBox(height: 32),
        ],
      ),
    );
  }
  Widget _buildHeaderMetrics(FullAnalysisResult result) {
    // Format splits & breakdown
    String splitText = "-";
    double splitFontSize = 18; // Default size

    final breakdown = result.splitTiming?.metadata?['split_breakdown'];
    if (breakdown != null && breakdown is Map) {
      // Sort keys to ensure order 0-15 -> 15-25 -> 25-50
      final sortedKeys = breakdown.keys.toList()..sort();
      final List<String> lines = [];
      for (var k in sortedKeys) {
        lines.add("$k: ${breakdown[k]}");
      }
      splitText = lines.join("\n");
      splitFontSize = 11; // Smaller font for multi-line details
    } else {
      final splitsList = result.splitTiming?.splits ?? [];
      if (splitsList.isNotEmpty) {
        splitText = splitsList.map((s) => s.toStringAsFixed(1)).join(" / ") + " s";
      }
    }
    
    // Strokes Text & Label
    String strokesText = "${result.strokeResult.range1RecoveryCount ?? 0} / ${result.strokeResult.range2RecoveryCount ?? 0}";
    String strokesLabel = "Strokes (Out/In)";

    final strokesBd = result.strokeResult.metadata?['strokes_breakdown'];
    if (strokesBd != null && strokesBd is String) {
        strokesText = strokesBd;
        final count = strokesBd.split('/').length;
        if (count > 0) {
           final laps = List.generate(count, (i) => "Lap ${i+1}").join('/');
           strokesLabel = "Strokes ($laps)";
        }
    }
    
    // SPM Text & Label
    String spmText = (result.strokeResult.strokesPerMinute ?? 0).toStringAsFixed(1);
    String spmLabel = "SPM";

    final spmBd = result.splitTiming?.metadata?['spm_breakdown'];
    if (spmBd != null && spmBd is String) {
      spmText = spmBd;
      final count = spmBd.split('/').length;
      if (count > 1) { // Only change label if multiple parts
          final laps = List.generate(count, (i) => "Lap ${i+1}").join('/');
          spmLabel = "SPM ($laps)";
      }
    }

    return Row(
      children: [
        Expanded(child: _metricTile("Stroke Style", result.strokeStyle.toUpperCase())),
        SizedBox(width: 8),
        Expanded(child: _metricTile("Avg Speed", "${result.splitTiming?.averageSpeed?.toStringAsFixed(2) ?? '-'} m/s")),
        SizedBox(width: 8),
        Expanded(child: _metricTile(spmLabel, spmText)),
        SizedBox(width: 8),
        Expanded(child: _metricTile(strokesLabel, strokesText)),
        SizedBox(width: 8),
        Expanded(child: _metricTile("Split Timings", splitText, valueFontSize: splitFontSize)),
      ],
    );
  }

  // State for Phase Replay
  double? _loopStart;
  double? _loopEnd;
  VoidCallback? _loopListener;

  void _handlePhaseReplay(double startS, double endS) {
    if (_videoPlayerController == null) return;

    // 1. Toggle Off if clicking same region
    if (_loopStart == startS && _loopEnd == endS) {
      _stopLooping();
      return;
    }

    // 2. Start new Loop
    _stopLooping(); // Clear previous
    
    setState(() {
      _loopStart = startS;
      _loopEnd = endS;
    });

    // Seek and Play
    _videoPlayerController!.seekTo(Duration(milliseconds: (startS * 1000).toInt()));
    _videoPlayerController!.play();

    // Add Listener for Loop
    _loopListener = () {
      if (_videoPlayerController == null || _loopEnd == null) return;
      
      final currentPos = _videoPlayerController!.value.position.inMilliseconds / 1000.0;
      if (currentPos >= _loopEnd!) {
        // Loop back to start
        _videoPlayerController!.seekTo(Duration(milliseconds: (_loopStart! * 1000).toInt()));
      }
    };
    
    _videoPlayerController!.addListener(_loopListener!);
    
    // Show Feedback (Optional)
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text("Replaying Phase: ${startS.toStringAsFixed(1)}s - ${endS.toStringAsFixed(1)}s (Tap again to stop)"),
      duration: Duration(seconds: 2),
    ));
  }

  void _stopLooping() {
    if (_loopListener != null && _videoPlayerController != null) {
      _videoPlayerController!.removeListener(_loopListener!);
    }
    _videoPlayerController?.pause();
    setState(() {
      _loopStart = null;
      _loopEnd = null;
      _loopListener = null;
    });
  }

  Widget _metricTile(String label, String value, {double valueFontSize = 18}) {
    return Container(
      padding: EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(
            label, 
            style: TextStyle(
              color: Colors.grey[600], 
              fontSize: 12, 
              fontWeight: FontWeight.w500
            ),
            textAlign: TextAlign.center,
          ),
          SizedBox(height: 4),
          Text(
            value, 
            style: TextStyle(
              color: Colors.black87, 
              fontSize: valueFontSize, 
              fontWeight: FontWeight.bold
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

// Ensure the helper class is OUTSIDE the State class
class _ChartTabItem {
  final String originalKey;
  final InteractivePlot plot;
  final int realLapIndex;
  final String subType;
  final int typeOrder;
  final bool isKickAngle;
  String displayLabel = "";

  _ChartTabItem({
    required this.originalKey,
    required this.plot,
    required this.realLapIndex,
    required this.subType,
    required this.typeOrder,
    required this.isKickAngle
  });
}
