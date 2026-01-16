import 'dart:convert';

// ===== Upload & Status =====

class AnalysisUploadResponse {
  final String videoId;
  final String message;
  final String statusEndpoint;

  AnalysisUploadResponse({
    required this.videoId,
    required this.message,
    required this.statusEndpoint,
  });

  factory AnalysisUploadResponse.fromJson(Map<String, dynamic> json) {
    return AnalysisUploadResponse(
      videoId: json['video_id'],
      message: json['message'],
      statusEndpoint: json['status_endpoint'],
    );
  }
}

class AnalysisStatusResponse {
  final String videoId;
  final String filename;
  final String status;
  final int? progress;
  final String? errorMessage;

  AnalysisStatusResponse({
    required this.videoId,
    required this.filename,
    required this.status,
    this.progress,
    this.errorMessage,
  });

  factory AnalysisStatusResponse.fromJson(Map<String, dynamic> json) {
    return AnalysisStatusResponse(
      videoId: json['video_id'],
      filename: json['filename'],
      status: json['status'],
      progress: json['progress'],
      errorMessage: json['error_message'],
    );
  }
}

// ===== Chart Data Structures =====

class TimeSeriesDataPoint {
  final int frame;
  final double timestampMs;
  final double value;
  final String? phase;

  TimeSeriesDataPoint({
    required this.frame,
    required this.timestampMs,
    required this.value,
    this.phase,
  });

  factory TimeSeriesDataPoint.fromJson(Map<String, dynamic> json) {
    return TimeSeriesDataPoint(
      frame: json['frame'],
      timestampMs: json['timestamp_ms']?.toDouble(),
      value: json['value']?.toDouble(),
      phase: json['phase'],
    );
  }
}

class InteractivePlot {
  final String plotType; // "phase" | "angle"
  final Map<String, dynamic>? timeSeries; // Keep as map for flexible parsing or parse deeper
  final List<TimeSeriesDataPoint> dataPoints;
  final String title;

  InteractivePlot({
    required this.plotType,
    this.timeSeries,
    required this.dataPoints,
    required this.title,
  });

  factory InteractivePlot.fromJson(Map<String, dynamic> json) {
    List<TimeSeriesDataPoint> points = [];
    String title = "";
    
    // Parse time_series dictionary if present
    if (json['time_series'] != null) {
      final ts = json['time_series'];
      title = ts['title'] ?? "";
      if (ts['data_points'] != null) {
        points = (ts['data_points'] as List)
            .map((e) => TimeSeriesDataPoint.fromJson(e))
            .toList();
      }
    }

    return InteractivePlot(
      plotType: json['plot_type'] ?? "unknown",
      timeSeries: json['time_series'],
      dataPoints: points,
      title: title,
    );
  }
}

// ===== Analysis Results =====

class StrokePhaseInfo {
  final String phaseName;
  final int startFrame;
  final int endFrame;
  final double? durationMs;

  StrokePhaseInfo({
    required this.phaseName,
    required this.startFrame,
    required this.endFrame,
    this.durationMs,
  });

  factory StrokePhaseInfo.fromJson(Map<String, dynamic> json) {
    return StrokePhaseInfo(
      phaseName: json['phase_name'],
      startFrame: json['start_frame'],
      endFrame: json['end_frame'],
      durationMs: json['duration_ms']?.toDouble(),
    );
  }
}

class StrokeAnalysisResult {
  final int totalCount;
  final String strokeStyle;
  final int? range1RecoveryCount;
  final int? range2RecoveryCount;
  final double? strokesPerMinute;
  final double? averageStrokeDurationMs;
  final Map<String, List<StrokePhaseInfo>>? phases;

  StrokeAnalysisResult({
    required this.totalCount,
    required this.strokeStyle,
    this.range1RecoveryCount,
    this.range2RecoveryCount,
    this.strokesPerMinute,
    this.averageStrokeDurationMs,
    this.phases,
  });

  factory StrokeAnalysisResult.fromJson(Map<String, dynamic> json) {
    Map<String, List<StrokePhaseInfo>>? parsedPhases;
    if (json['phases'] != null) {
      parsedPhases = {};
      (json['phases'] as Map<String, dynamic>).forEach((key, value) {
        parsedPhases![key] = (value as List).map((i) => StrokePhaseInfo.fromJson(i)).toList();
      });
    }

    return StrokeAnalysisResult(
      totalCount: json['total_count'],
      strokeStyle: json['stroke_style'],
      range1RecoveryCount: json['range1_recovery_count'],
      range2RecoveryCount: json['range2_recovery_count'],
      strokesPerMinute: json['strokes_per_minute']?.toDouble(),
      averageStrokeDurationMs: json['average_stroke_duration_ms']?.toDouble(),
      phases: parsedPhases,
    );
  }
}

class SplitTimingResult {
  final List<double> splits;
  final double? averageSpeed;
  
  SplitTimingResult({
    required this.splits,
    this.averageSpeed,
  });

  factory SplitTimingResult.fromJson(Map<String, dynamic> json) {
    return SplitTimingResult(
      splits: List<double>.from(json['splits'].map((x) => x.toDouble())),
      averageSpeed: json['average_speed']?.toDouble(),
    );
  }
}

class CommonAnalysisData {
  final Map<String, dynamic> rawData;

  CommonAnalysisData(this.rawData);

  factory CommonAnalysisData.fromJson(Map<String, dynamic> json) {
    return CommonAnalysisData(json);
  }
}

class FullAnalysisResult {
  final String videoId;
  final String processedVideoPath;
  final String strokeStyle;
  final StrokeAnalysisResult strokeResult;
  final CommonAnalysisData? divingAnalysis;
  final SplitTimingResult? splitTiming;
  final String? focusCropVideoPath;
  final String timestamp;
  
  // Charts
  final Map<String, InteractivePlot>? strokePlotFigs;
  final Map<String, InteractivePlot>? divingPlotFigs;

  FullAnalysisResult({
    required this.videoId,
    required this.processedVideoPath,
    required this.strokeStyle,
    required this.strokeResult,
    this.divingAnalysis,
    this.splitTiming,
    this.focusCropVideoPath,
    required this.timestamp,
    this.strokePlotFigs,
    this.divingPlotFigs,
  });

  factory FullAnalysisResult.fromJson(Map<String, dynamic> json) {
    // Helper to parse map of plots
    Map<String, InteractivePlot>? parsePlots(Map<String, dynamic>? data) {
      if (data == null) return null;
      var map = <String, InteractivePlot>{};
      data.forEach((k, v) {
        map[k] = InteractivePlot.fromJson(v);
      });
      return map;
    }

    return FullAnalysisResult(
      videoId: json['video_id'],
      processedVideoPath: json['processed_video_path'],
      strokeStyle: json['stroke_style'],
      strokeResult: StrokeAnalysisResult.fromJson(json['stroke_result']),
      divingAnalysis: json['diving_analysis'] != null 
          ? CommonAnalysisData.fromJson(json['diving_analysis']) 
          : null,
      splitTiming: json['split_timing'] != null 
          ? SplitTimingResult.fromJson(json['split_timing']) 
          : null,
      focusCropVideoPath: json['focus_crop_video_path'],
      timestamp: json['timestamp'],
      strokePlotFigs: parsePlots(json['stroke_plot_figs']),
      divingPlotFigs: parsePlots(json['diving_plot_figs']),
    );
  }
}
