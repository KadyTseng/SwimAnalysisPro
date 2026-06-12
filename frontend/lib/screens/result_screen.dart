import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:math' as math;
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
        hideControlsTimer: const Duration(milliseconds: 300),
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

  void _showMetricsDialog(BuildContext context, FullAnalysisResult result) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Container(
            width: math.max(MediaQuery.of(context).size.width * 0.8, 600.0),
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.analytics, color: Colors.blueAccent, size: 28),
                        SizedBox(width: 8),
                        Text(
                          "分析指標數據 (Metrics Summary)",
                          style: TextStyle(
                            fontSize: 20, 
                            fontWeight: FontWeight.bold, 
                            color: Colors.blueGrey[900]
                          ),
                        ),
                      ],
                    ),
                    IconButton(
                      icon: Icon(Icons.close),
                      onPressed: () => Navigator.of(context).pop(),
                    )
                  ],
                ),
                Divider(height: 32),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: _buildHeaderMetrics(result),
                ),
                SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.result;

    // Calculate aspect ratio dynamically or default to 16:9
    final double aspectRatio = _isVideoInitialized && _videoPlayerController != null && _videoPlayerController!.value.aspectRatio > 0
        ? _videoPlayerController!.value.aspectRatio
        : 3840 / 1080; // 32:9 widescreen default
    
    final screenWidth = MediaQuery.of(context).size.width;
    
    // Stretch to 100% of horizontal webpage width
    double videoHeight = screenWidth / aspectRatio;

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Custom Header (Not pinned, scrolls with content)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 16.0),
                    child: Row(
                      children: [
                        IconButton(
                          icon: Icon(Icons.arrow_back),
                          onPressed: () => Navigator.of(context).pop(),
                        ),
                        Expanded(
                          child: Center(
                            child: Text(
                              'Swim Analysis Dashboard',
                              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.blueGrey[900]
                              ),
                            ),
                          ),
                        ),
                        // 1. Collapsible Metrics Toggle Button in Header
                        TextButton.icon(
                          onPressed: () => _showMetricsDialog(context, result),
                          icon: Icon(Icons.analytics, color: Colors.blueAccent),
                          label: Text("顯示分析指標", style: TextStyle(color: Colors.blueAccent, fontWeight: FontWeight.bold)),
                          style: TextButton.styleFrom(
                            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            backgroundColor: Colors.blue[50],
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          ),
                        ),
                        SizedBox(width: 12),
                        IconButton(
                          icon: Icon(Icons.download, color: Colors.blueAccent),
                          onPressed: () => launchUrl(Uri.parse(_apiService.getDownloadUrl(result.videoId))),
                          tooltip: 'Download Video',
                        ),
                      ],
                    ),
                  ),

                  Divider(height: 1),
                ],
              ),
            ),

            // 2. Video Player Section (Sticky & Stretched to 100% width)
            SliverPersistentHeader(
              pinned: true,
              delegate: _StickyVideoDelegate(
                maxHeight: videoHeight,
                minHeight: videoHeight, // Fixed size, doesn't shrink
                child: Container(
                  width: double.infinity,
                  color: Colors.white, // background color set to white
                  child: _isVideoInitialized
                      ? AspectRatio(
                          aspectRatio: _videoPlayerController!.value.aspectRatio,
                          child: Stack(
                            alignment: Alignment.center,
                            children: [
                              // 1. Natural Video Player
                              Chewie(controller: _chewieController!),
                            
                              // PiP Focus Window
                            if (_showFocusPiP && _isFocusInitialized && _focusVideoController!.value.isInitialized)
                              Positioned(
                                top: 10,
                                right: 10,
                                width: _focusVideoController!.value.size.width * 0.7,
                                height: _focusVideoController!.value.size.height * 0.7,
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
                      : Center(child: CircularProgressIndicator(color: Colors.blueAccent)),
                ),
              ),
            ),

            // 3. Charts/Waveforms Section (Displayed BELOW video) with Tabs
            SliverToBoxAdapter(
              child: ((result.strokePlotFigs?.isNotEmpty ?? false) || (result.divingPlotFigs?.isNotEmpty ?? false))
                  ? _buildChartTabs(context, result)
                  : Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('No waveform data available for this analysis.'),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  InteractivePlot _generateSpeedPlot({
    required int lapIndex,
    required int startFrame,
    required int endFrame,
    required double avgSpeedVal,
    required double fps,
    required bool isDecreasing,
    InteractivePlot? trackerPlot,
  }) {
    final List<TimeSeriesDataPoint> points = [];
    final int totalFrames = endFrame - startFrame;
    if (totalFrames <= 0) return InteractivePlot(plotType: "speed", dataPoints: [], title: "Lap $lapIndex Speed");

    final double cruiseSpeed = avgSpeedVal > 0 ? avgSpeedVal : 1.5;

    // 1. Populate raw distances and times for all frames in this lap
    final List<double> distances = [];
    final List<double> times = [];
    for (int i = 0; i <= totalFrames; i++) {
      final int f = startFrame + i;
      times.add(i / fps);

      double d = 0;
      if (trackerPlot != null && trackerPlot.dataPoints.isNotEmpty) {
        final closestPoint = trackerPlot.dataPoints.reduce((a, b) =>
            (a.frame - f).abs() < (b.frame - f).abs() ? a : b);
        final double X = closestPoint.value;
        if (isDecreasing) {
          d = (3840.0 - X) * 25.0 / 3840.0;
        } else {
          d = 25.0 + X * 25.0 / 3840.0;
        }
      } else {
        if (isDecreasing) {
          d = 25.0 * (i / totalFrames);
        } else {
          d = 25.0 + 25.0 * (i / totalFrames);
        }
      }
      distances.add(d);
    }

    // 2. Enforce monotonic non-decreasing on distances
    final List<double> monoDistances = List.from(distances);
    double maxD = isDecreasing ? 0.0 : 25.0;
    for (int i = 0; i < monoDistances.length; i++) {
      double d = monoDistances[i];
      if (isDecreasing) {
        if (d < 0) d = 0;
        if (d > 25.0) d = 25.0;
        if (d <= maxD) {
          d = maxD + 1e-5;
        }
        maxD = d;
      } else {
        if (d < 25.0) d = 25.0;
        if (d > 50.0) d = 50.0;
        if (d <= maxD) {
          d = maxD + 1e-5;
        }
        maxD = d;
      }
      monoDistances[i] = d;
    }

    // 3. Compute raw speed (frame-by-frame derivative with diff window = 3 to reduce pixel jitter)
    final List<double> rawSpeeds = List.filled(distances.length, cruiseSpeed);
    const int diffWindow = 3;
    for (int i = 0; i < monoDistances.length; i++) {
      int leftIdx = (i - diffWindow ~/ 2).clamp(0, monoDistances.length - 1);
      int rightIdx = (i + diffWindow ~/ 2).clamp(0, monoDistances.length - 1);
      double distDiff = (monoDistances[rightIdx] - monoDistances[leftIdx]).abs();
      double timeDiff = times[rightIdx] - times[leftIdx];
      if (timeDiff > 0) {
        rawSpeeds[i] = distDiff / timeDiff;
      } else {
        rawSpeeds[i] = cruiseSpeed;
      }
      
      // Outlier filtering (-2.0 to 4.0 m/s)
      if (rawSpeeds[i] < -2.0) rawSpeeds[i] = -2.0;
      if (rawSpeeds[i] > 4.0) rawSpeeds[i] = 4.0;
    }

    // 4. Smooth speed values using a rolling mean with SMOOTH_WINDOW = 25
    final List<double> smoothedSpeeds = List.filled(distances.length, cruiseSpeed);
    const int smoothWindow = 25;
    for (int i = 0; i < rawSpeeds.length; i++) {
      double sum = 0;
      int count = 0;
      for (int w = -smoothWindow ~/ 2; w <= smoothWindow ~/ 2; w++) {
        int idx = i + w;
        if (idx >= 0 && idx < rawSpeeds.length) {
          sum += rawSpeeds[idx];
          count++;
        }
      }
      smoothedSpeeds[i] = sum / count;
    }

    // 5. Populate TimeSeriesDataPoints
    for (int i = 0; i <= totalFrames; i++) {
      final int f = startFrame + i;
      final double tMs = (f / fps) * 1000.0;
      final double relativeTimeSec = i / fps;
      final double finalSpeed = smoothedSpeeds[i];

      points.add(TimeSeriesDataPoint(
        frame: f,
        timestampMs: tMs,
        value: finalSpeed,
        phase: "${monoDistances[i]}|$relativeTimeSec",
      ));
    }

    return InteractivePlot(
      plotType: "speed",
      timeSeries: {
        "metadata": {
          "reverse_axis": isDecreasing,
        }
      },
      dataPoints: points,
      title: "Lap $lapIndex Speed",
    );
  }

  Widget _buildChartTabs(BuildContext context, FullAnalysisResult result) {
    List<_ChartTabItem> tabs = [];

    // 1. Gather all unique raw lap indices from stroke and diving plot keys
    final Set<int> rawLapIndices = {};
    void _collectLapIndices(Map<String, dynamic>? figs) {
      if (figs == null) return;
      for (var key in figs.keys) {
        final match = RegExp(r"lap\s*(\d+)").firstMatch(key.toLowerCase());
        if (match != null) {
          rawLapIndices.add(int.parse(match.group(1)!));
        }
      }
    }
    _collectLapIndices(result.strokePlotFigs);
    _collectLapIndices(result.divingPlotFigs);

    // Sort original lap indices in ascending order
    final sortedRawLapIndices = rawLapIndices.toList()..sort();

    // Create a map from original lap index to sequential renumbered index (1, 2, 3...)
    final Map<int, int> lapMapping = {};
    for (int i = 0; i < sortedRawLapIndices.length; i++) {
      lapMapping[sortedRawLapIndices[i]] = i + 1;
    }

    final double fps = result.fps;

    // Try to parse split times
    final breakdown = result.splitTiming?.metadata?['split_breakdown'];
    double t0_15 = 8.5;
    double t15_25 = 7.5;
    double t25_50 = 15.0;

    if (breakdown != null && breakdown is Map) {
      if (breakdown.containsKey('0-15m')) {
        t0_15 = double.tryParse(breakdown['0-15m'].toString().replaceAll('s', '')) ?? 8.5;
      }
      if (breakdown.containsKey('15-25m')) {
        t15_25 = double.tryParse(breakdown['15-25m'].toString().replaceAll('s', '')) ?? 7.5;
      }
      if (breakdown.containsKey('25-50m')) {
        t25_50 = double.tryParse(breakdown['25-50m'].toString().replaceAll('s', '')) ?? 15.0;
      }
    }

    if (sortedRawLapIndices.isNotEmpty) {
      for (var origIdx in sortedRawLapIndices) {
        final int seqIdx = lapMapping[origIdx]!;
        
        // Find bbox_center plot first for precise speed calculation, then fallback to hip or shoulder plots
        final bboxKey = result.strokePlotFigs?.keys.firstWhere(
          (k) => k.toLowerCase().contains("lap$origIdx") && (k.toLowerCase().contains("bbox") || k.toLowerCase().contains("center")),
          orElse: () => "",
        ) ?? "";

        final hipKey = result.strokePlotFigs?.keys.firstWhere(
          (k) => k.toLowerCase().contains("lap$origIdx") && k.toLowerCase().contains("hip"),
          orElse: () => "",
        ) ?? "";
        
        final shoulderKey = result.strokePlotFigs?.keys.firstWhere(
          (k) => k.toLowerCase().contains("lap$origIdx") && k.toLowerCase().contains("shoulder"),
          orElse: () => "",
        ) ?? "";

        final trackerPlot = (bboxKey.isNotEmpty)
            ? result.strokePlotFigs![bboxKey]
            : ((hipKey.isNotEmpty) 
                ? result.strokePlotFigs![hipKey] 
                : ((shoulderKey.isNotEmpty) ? result.strokePlotFigs![shoulderKey] : null));

        final matchingKey = bboxKey.isNotEmpty 
            ? bboxKey 
            : (hipKey.isNotEmpty 
                ? hipKey 
                : (shoulderKey.isNotEmpty ? shoulderKey : ""));

        int startF = 0;
        int endF = 1000;
        bool isDecreasing = (seqIdx % 2 == 1); // Alternating directions as fallback

        if (matchingKey.isNotEmpty) {
          isDecreasing = matchingKey.toLowerCase().contains("decreasing") || matchingKey.toLowerCase().contains("range1");
        }

        final plotForRange = trackerPlot ?? (matchingKey.isNotEmpty ? result.strokePlotFigs![matchingKey] : null);
        if (plotForRange != null && plotForRange.dataPoints.isNotEmpty) {
          startF = plotForRange.dataPoints.map((dp) => dp.frame).reduce((a, b) => a < b ? a : b);
          endF = plotForRange.dataPoints.map((dp) => dp.frame).reduce((a, b) => a > b ? a : b);
        }

        // Match average speed for this specific sequential lap
        double avgSpeed = 1.5;
        if (seqIdx == 1) {
          avgSpeed = 25.0 / (t0_15 + t15_25);
        } else if (seqIdx == 2) {
          avgSpeed = 25.0 / t25_50;
        } else {
          avgSpeed = result.splitTiming?.averageSpeed ?? 1.5;
        }

        final speedPlot = _generateSpeedPlot(
          lapIndex: seqIdx, 
          startFrame: startF, 
          endFrame: endF, 
          avgSpeedVal: avgSpeed, 
          fps: fps, 
          isDecreasing: isDecreasing,
          trackerPlot: trackerPlot,
        );

        tabs.add(_ChartTabItem(
          originalKey: "lap${seqIdx}_speed",
          plot: speedPlot,
          realLapIndex: seqIdx,
          subType: "Speed",
          typeOrder: -1, // Prepend speed tabs at the very start of each lap
          isKickAngle: false,
        ));
      }
    } else {
      // Fallback: if backend didn't provide laps_data, build them from duration
      final totalDurationMs = _videoPlayerController?.value.duration.inMilliseconds ?? 30000;
      final int totalFrames = totalDurationMs ~/ 33;
      
      // Lap 1 Outbound
      final int midFrame = totalFrames ~/ 2;
      final double avgSpeed1 = 25.0 / (t0_15 + t15_25);
      final speedPlot1 = _generateSpeedPlot(
        lapIndex: 1, 
        startFrame: 0, 
        endFrame: midFrame, 
        avgSpeedVal: avgSpeed1, 
        fps: fps, 
        isDecreasing: true,
      );
      tabs.add(_ChartTabItem(
        originalKey: "lap1_speed",
        plot: speedPlot1,
        realLapIndex: 1,
        subType: "Speed",
        typeOrder: -1,
        isKickAngle: false,
      ));

      // Lap 2 Inbound
      final double avgSpeed2 = 25.0 / t25_50;
      final speedPlot2 = _generateSpeedPlot(
        lapIndex: 2, 
        startFrame: midFrame, 
        endFrame: totalFrames, 
        avgSpeedVal: avgSpeed2, 
        fps: fps, 
        isDecreasing: false,
      );
      tabs.add(_ChartTabItem(
        originalKey: "lap2_speed",
        plot: speedPlot2,
        realLapIndex: 2,
        subType: "Speed",
        typeOrder: -1,
        isKickAngle: false,
      ));
    }

    // Helper to parse and add other plots
    void addTab(String key, InteractivePlot plot, bool isKickAngle) {
      if (key.toLowerCase().contains("hip") || key.toLowerCase().contains("bbox") || key.toLowerCase().contains("center")) {
        return; // Don't add raw coordinate tracker plots to UI tabs
      }
      int lapIndex = 999;
      String typeStr = isKickAngle ? "Kick Angle" : "Unknown";
      int typeOrder = 0; 

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
          typeStr = "Info"; 
          typeOrder = 3;
        }
      }

      final lapMatch = RegExp(r"lap(\d+)").firstMatch(key.toLowerCase());
      if (lapMatch != null) {
        final originalLapIdx = int.parse(lapMatch.group(1)!);
        lapIndex = lapMapping[originalLapIdx] ?? originalLapIdx;
      } else {
        if (key.contains("range1") || key.contains("decreasing")) lapIndex = 1;
        else if (key.contains("range2") || key.contains("increasing")) lapIndex = 2;
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

    // Sort: Lap ASC -> TypeOrder ASC (Speed has typeOrder = -1, so it always goes first!)
    tabs.sort((a, b) {
      int cmp = a.realLapIndex.compareTo(b.realLapIndex);
      if (cmp != 0) return cmp;
      return a.typeOrder.compareTo(b.typeOrder);
    });

    // Generate Display Labels
    for (var tab in tabs) {
      tab.displayLabel = "Lap ${tab.realLapIndex} ${tab.subType}";
    }

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
            height: 350,
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

class _StickyVideoDelegate extends SliverPersistentHeaderDelegate {
  final Widget child;
  final double maxHeight;
  final double minHeight;

  _StickyVideoDelegate({required this.child, required this.maxHeight, required this.minHeight});

  @override
  double get minExtent => minHeight;

  @override
  double get maxExtent => maxHeight < minHeight ? minHeight : maxHeight;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return SizedBox.expand(child: child);
  }

  @override
  bool shouldRebuild(covariant _StickyVideoDelegate oldDelegate) {
    return oldDelegate.maxHeight != maxHeight || 
           oldDelegate.minHeight != minHeight || 
           oldDelegate.child != child;
  }
}
