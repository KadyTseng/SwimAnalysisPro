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
    _videoPlayerController?.dispose();
    _chewieController?.dispose();
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
                color: Colors.black,
                child: _isVideoInitialized
                    ? Chewie(controller: _chewieController!)
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
    // Collect all plots
    final Map<String, InteractivePlot> allPlots = {};
    
    // Add Stroke Plots with clear names
    result.strokePlotFigs?.forEach((key, value) {
      allPlots["Stroke $key"] = value;
    });

    // Add Diving Plots
    result.divingPlotFigs?.forEach((key, value) {
      allPlots["Kick Angle $key"] = value;
    });

    // Debugging Info for Terminal
    print("\n--------------------------------------------------");
    print("DEBUG: Chart Data Loaded");
    allPlots.forEach((key, val) {
      print("  >> Plot Key: $key");
      print("     - Points: ${val.dataPoints.length}");
      print("     - Phase Samples (First 5): ${val.dataPoints.take(5).map((e) => e.phase).toList()}");
    });
    print("--------------------------------------------------\n");

    if (allPlots.isEmpty) return SizedBox.shrink();

    return DefaultTabController(
      length: allPlots.length,
      child: Column(
        children: [
          Container(
            color: Colors.grey[100],
            child: TabBar(
              isScrollable: true,
              labelColor: Colors.blueAccent,
              unselectedLabelColor: Colors.grey,
              indicatorColor: Colors.blueAccent,
              tabs: allPlots.keys.map((title) => Tab(text: title)).toList(),
            ),
          ),
          Container(
            height: 500, // Increased height to prevent overflow
            padding: EdgeInsets.all(16),
            child: TabBarView(
              children: allPlots.values.map((plot) {
                return AnalysisChartWidget(
                  plotData: plot, 
                  lineColor: plot.plotType == 'angle' ? Colors.orangeAccent : Colors.blueAccent,
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
    // Format splits: e.g. "25.5s"
    final splitsList = result.splitTiming?.splits ?? [];
    String splitText = splitsList.isNotEmpty ? splitsList.map((s) => s.toStringAsFixed(1)).join(" / ") + " s" : "-";
    
    // Stroke Counts: Out / Return
    final r1 = result.strokeResult.range1RecoveryCount ?? 0;
    final r2 = result.strokeResult.range2RecoveryCount ?? 0;
    String strokesText = "$r1 / $r2";

    return Row(
      children: [
        Expanded(child: _metricTile("Stroke Style", result.strokeStyle.toUpperCase())),
        SizedBox(width: 8),
        Expanded(child: _metricTile("Avg Speed", "${result.splitTiming?.averageSpeed?.toStringAsFixed(2) ?? '-'} m/s")),
        SizedBox(width: 8),
        Expanded(child: _metricTile("SPM", (result.strokeResult.strokesPerMinute ?? 0).toStringAsFixed(1))),
        SizedBox(width: 8),
        Expanded(child: _metricTile("Strokes (Out/In)", strokesText)),
        SizedBox(width: 8),
        Expanded(child: _metricTile("Split Timings", splitText)),
      ],
    );
  }

  Widget _metricTile(String label, String value) {
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
              fontSize: 18, 
              fontWeight: FontWeight.bold
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
