import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models.dart';

/// Data model for a single stroke's 2D wrist trajectory
class StrokeTrajectory {
  final int strokeIndex;
  final String strokeName;
  final int lapIndex;
  final int startFrame;
  final int endFrame;
  final int durationFrames;
  final double startTimeS;
  final double endTimeS;
  final double durationS;
  final List<Offset> rawPoints;
  final List<Offset> smoothPoints;
  final Offset startPoint;
  final Offset endPoint;
  final Offset shoulderPoint;

  StrokeTrajectory({
    required this.strokeIndex,
    required this.strokeName,
    required this.lapIndex,
    required this.startFrame,
    required this.endFrame,
    required this.durationFrames,
    required this.startTimeS,
    required this.endTimeS,
    required this.durationS,
    required this.rawPoints,
    required this.smoothPoints,
    required this.startPoint,
    required this.endPoint,
    required this.shoulderPoint,
  });

  factory StrokeTrajectory.fromJson(Map<String, dynamic> json) {
    List<Offset> parseOffsets(dynamic list) {
      if (list == null) return [];
      return (list as List).map((pt) {
        if (pt is Map) {
          final x = (pt['x'] as num?)?.toDouble() ?? 0.0;
          final y = (pt['y'] as num?)?.toDouble() ?? 0.0;
          return Offset(x, y);
        } else if (pt is List && pt.length >= 2) {
          return Offset((pt[0] as num).toDouble(), (pt[1] as num).toDouble());
        }
        return Offset.zero;
      }).toList();
    }

    Offset parseSingleOffset(dynamic pt) {
      if (pt is Map) {
        return Offset(
          (pt['x'] as num?)?.toDouble() ?? 0.0,
          (pt['y'] as num?)?.toDouble() ?? 0.0,
        );
      }
      return Offset.zero;
    }

    return StrokeTrajectory(
      strokeIndex: json['stroke_index'] ?? 1,
      strokeName: json['stroke_name'] ?? 'Stroke ${json['stroke_index'] ?? 1}',
      lapIndex: json['lap_index'] ?? 1,
      startFrame: json['start_frame'] ?? 0,
      endFrame: json['end_frame'] ?? 0,
      durationFrames: json['duration_frames'] ?? 0,
      startTimeS: (json['start_time_s'] as num?)?.toDouble() ?? 0.0,
      endTimeS: (json['end_time_s'] as num?)?.toDouble() ?? 0.0,
      durationS: (json['duration_s'] as num?)?.toDouble() ?? 0.0,
      rawPoints: parseOffsets(json['raw_points']),
      smoothPoints: parseOffsets(json['smooth_points']),
      startPoint: parseSingleOffset(json['start_point']),
      endPoint: parseSingleOffset(json['end_point']),
      shoulderPoint: parseSingleOffset(json['shoulder_point']),
    );
  }
}

/// Interactive 2D Wrist Trajectory Widget with fixed Shoulder (0, 0) origin at center
class WristTrajectoryWidget extends StatefulWidget {
  final InteractivePlot plotData;
  final ValueNotifier<double>? currentTimeNotifier;
  final Function(double startS, double endS)? onPhaseTap;

  const WristTrajectoryWidget({
    Key? key,
    required this.plotData,
    this.currentTimeNotifier,
    this.onPhaseTap,
  }) : super(key: key);

  @override
  _WristTrajectoryWidgetState createState() => _WristTrajectoryWidgetState();
}

class _WristTrajectoryWidgetState extends State<WristTrajectoryWidget> {
  List<StrokeTrajectory> _strokes = [];
  int _selectedStrokeIndex = 0;
  bool _autoSyncWithVideo = true;
  bool _showRawPoints = true;
  double _currentVideoTime = 0.0;
  Offset? _hoverCoord;

  @override
  void initState() {
    super.initState();
    _parseStrokes();

    // Listen to video playback position for real-time stroke sync
    widget.currentTimeNotifier?.addListener(_onTimeUpdate);
  }

  @override
  void didUpdateWidget(covariant WristTrajectoryWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.plotData != widget.plotData) {
      _parseStrokes();
    }
    if (oldWidget.currentTimeNotifier != widget.currentTimeNotifier) {
      oldWidget.currentTimeNotifier?.removeListener(_onTimeUpdate);
      widget.currentTimeNotifier?.addListener(_onTimeUpdate);
    }
  }

  @override
  void dispose() {
    widget.currentTimeNotifier?.removeListener(_onTimeUpdate);
    super.dispose();
  }

  void _parseStrokes() {
    final metadata = widget.plotData.timeSeries?['metadata'];
    if (metadata != null && metadata['strokes'] != null) {
      final strokesRaw = metadata['strokes'] as List;
      _strokes = strokesRaw.map((e) => StrokeTrajectory.fromJson(e)).toList();
    } else {
      _strokes = [];
    }
    _selectedStrokeIndex = 0;
  }

  void _onTimeUpdate() {
    if (!mounted || _strokes.isEmpty) return;
    final t = widget.currentTimeNotifier?.value ?? 0.0;
    _currentVideoTime = t;

    if (_autoSyncWithVideo) {
      // Find stroke matching the current video time
      for (int i = 0; i < _strokes.length; i++) {
        final s = _strokes[i];
        if (t >= s.startTimeS && t <= s.endTimeS) {
          if (_selectedStrokeIndex != i) {
            setState(() {
              _selectedStrokeIndex = i;
            });
          } else {
            // Re-render to update tracking bead position along the curve
            setState(() {});
          }
          return;
        }
      }
    } else {
      // If within current stroke, re-render bead
      final cur = _strokes[_selectedStrokeIndex];
      if (t >= cur.startTimeS && t <= cur.endTimeS) {
        setState(() {});
      }
    }
  }

  void _selectStroke(int index, {bool jumpVideo = true}) {
    if (index < 0 || index >= _strokes.length) return;
    setState(() {
      _selectedStrokeIndex = index;
    });

    if (jumpVideo) {
      final stroke = _strokes[index];
      widget.onPhaseTap?.call(stroke.startTimeS, stroke.endTimeS);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_strokes.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        alignment: Alignment.center,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.timeline, size: 48, color: Colors.blueGrey[300]),
            const SizedBox(height: 12),
            Text(
              '暫無划手軌跡資料 (No trajectory data available)',
              style: TextStyle(color: Colors.blueGrey[600], fontSize: 16),
            ),
          ],
        ),
      );
    }

    final currentStroke = _strokes[_selectedStrokeIndex];

    // Compute progress ratio (0.0 to 1.0) of current video position within this stroke
    double? progressInStroke;
    if (_currentVideoTime >= currentStroke.startTimeS && _currentVideoTime <= currentStroke.endTimeS) {
      final duration = currentStroke.endTimeS - currentStroke.startTimeS;
      if (duration > 0) {
        progressInStroke = (_currentVideoTime - currentStroke.startTimeS) / duration;
      }
    }

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1E222D), // Sleek dark aesthetic for contrast
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blueGrey.withOpacity(0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.15),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1. Control Header Bar
          _buildControlHeader(currentStroke),

          // 2. Trajectory Canvas (Fixed Origin at Center)
          Expanded(
            child: ClipRect(
              child: MouseRegion(
                onHover: (event) {
                  // Coordinate tracking on hover
                },
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return CustomPaint(
                      size: Size(constraints.maxWidth, constraints.maxHeight),
                      painter: _TrajectoryPainter(
                        stroke: currentStroke,
                        allStrokes: _strokes,
                        showRawPoints: _showRawPoints,
                        progressRatio: progressInStroke,
                      ),
                    );
                  },
                ),
              ),
            ),
          ),

          // 3. Bottom Information & Metric Bar
          _buildBottomMetrics(currentStroke),
        ],
      ),
    );
  }

  Widget _buildControlHeader(StrokeTrajectory currentStroke) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF151821),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.08))),
      ),
      child: Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 12,
        runSpacing: 8,
        children: [
          // Stroke Selector with Previous / Next Buttons
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                icon: const Icon(Icons.chevron_left, color: Colors.white70),
                tooltip: '前一下 (Previous Stroke)',
                onPressed: _selectedStrokeIndex > 0
                    ? () => _selectStroke(_selectedStrokeIndex - 1)
                    : null,
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.blueAccent.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blueAccent.withOpacity(0.4)),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: _selectedStrokeIndex,
                    dropdownColor: const Color(0xFF252A38),
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 15,
                    ),
                    icon: const Icon(Icons.arrow_drop_down, color: Colors.blueAccent),
                    items: List.generate(_strokes.length, (idx) {
                      final s = _strokes[idx];
                      return DropdownMenuItem<int>(
                        value: idx,
                        child: Text('${s.strokeName} (${s.startTimeS}s ~ ${s.endTimeS}s)'),
                      );
                    }),
                    onChanged: (val) {
                      if (val != null) _selectStroke(val);
                    },
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.chevron_right, color: Colors.white70),
                tooltip: '後一下 (Next Stroke)',
                onPressed: _selectedStrokeIndex < _strokes.length - 1
                    ? () => _selectStroke(_selectedStrokeIndex + 1)
                    : null,
              ),
              const SizedBox(width: 8),
              // Time & Frame badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '幀 ${currentStroke.startFrame} ~ ${currentStroke.endFrame} | 時長: ${currentStroke.durationS}s',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ),
            ],
          ),

          // Action Toggles: Auto-Sync & Raw Data
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Auto-Sync Toggle
              FilterChip(
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _autoSyncWithVideo ? Icons.sync : Icons.sync_disabled,
                      size: 16,
                      color: _autoSyncWithVideo ? Colors.greenAccent : Colors.white60,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '隨影片同步',
                      style: TextStyle(
                        fontSize: 12,
                        color: _autoSyncWithVideo ? Colors.white : Colors.white60,
                        fontWeight: _autoSyncWithVideo ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
                selected: _autoSyncWithVideo,
                selectedColor: Colors.green.withOpacity(0.25),
                backgroundColor: Colors.white.withOpacity(0.05),
                checkmarkColor: Colors.greenAccent,
                onSelected: (val) {
                  setState(() => _autoSyncWithVideo = val);
                },
              ),
              const SizedBox(width: 8),

              // Raw points toggle
              FilterChip(
                label: Text(
                  '原始點',
                  style: TextStyle(
                    fontSize: 12,
                    color: _showRawPoints ? Colors.white : Colors.white60,
                  ),
                ),
                selected: _showRawPoints,
                selectedColor: Colors.blueAccent.withOpacity(0.25),
                backgroundColor: Colors.white.withOpacity(0.05),
                checkmarkColor: Colors.blueAccent,
                onSelected: (val) {
                  setState(() => _showRawPoints = val);
                },
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBottomMetrics(StrokeTrajectory currentStroke) {
    // Calculate stroke bounds (relative displacement in pixels)
    double minX = 0, maxX = 0, minY = 0, maxY = 0;
    if (currentStroke.smoothPoints.isNotEmpty) {
      minX = currentStroke.smoothPoints.map((p) => p.dx).reduce(math.min);
      maxX = currentStroke.smoothPoints.map((p) => p.dx).reduce(math.max);
      minY = currentStroke.smoothPoints.map((p) => p.dy).reduce(math.min);
      maxY = currentStroke.smoothPoints.map((p) => p.dy).reduce(math.max);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF151821),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(12)),
        border: Border(top: BorderSide(color: Colors.white.withOpacity(0.08))),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Legend
          Row(
            children: [
              _buildLegendItem(const Color(0xFFFF5252), '肩膀 (0, 0) 原點', isCross: true),
              const SizedBox(width: 14),
              _buildLegendItem(const Color(0xFF00E676), '起點 Start', isCircle: true),
              const SizedBox(width: 14),
              _buildLegendItem(const Color(0xFFE040FB), '終點 End', isSquare: true),
              const SizedBox(width: 14),
              _buildLegendItem(const Color(0xFF00B0FF), '100點平滑軌跡', isLine: true),
              if (_showRawPoints) ...[
                const SizedBox(width: 14),
                _buildLegendItem(Colors.white38, '原始採樣點', isDot: true),
              ],
            ],
          ),

          // Metrics Pill
          Row(
            children: [
              _buildMetricBadge('最大前伸', '+${maxX.toStringAsFixed(1)} px', Colors.cyanAccent),
              const SizedBox(width: 8),
              _buildMetricBadge('最大後推', '${minX.toStringAsFixed(1)} px', Colors.amberAccent),
              const SizedBox(width: 8),
              _buildMetricBadge('最大深度', '${minY.toStringAsFixed(1)} px', Colors.blueAccent),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(Color color, String text,
      {bool isCross = false, bool isCircle = false, bool isSquare = false, bool isLine = false, bool isDot = false}) {
    Widget iconWidget;
    if (isCross) {
      iconWidget = Icon(Icons.close, size: 14, color: color);
    } else if (isCircle) {
      iconWidget = Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      );
    } else if (isSquare) {
      iconWidget = Container(
        width: 9,
        height: 9,
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
      );
    } else if (isLine) {
      iconWidget = Container(width: 16, height: 3, color: color);
    } else {
      iconWidget = Container(
        width: 6,
        height: 6,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        iconWidget,
        const SizedBox(width: 5),
        Text(text, style: const TextStyle(color: Colors.white70, fontSize: 11)),
      ],
    );
  }

  Widget _buildMetricBadge(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$label: ', style: TextStyle(color: Colors.white60, fontSize: 11)),
          Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11)),
        ],
      ),
    );
  }
}

/// Custom painter for the 2D Wrist Trajectory with fixed origin at center
class _TrajectoryPainter extends CustomPainter {
  final StrokeTrajectory stroke;
  final List<StrokeTrajectory> allStrokes;
  final bool showRawPoints;
  final double? progressRatio;

  _TrajectoryPainter({
    required this.stroke,
    required this.allStrokes,
    required this.showRawPoints,
    this.progressRatio,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width <= 0 || size.height <= 0) return;

    final center = Offset(size.width / 2, size.height / 2);

    // Calculate maximum extent across all strokes to keep scale stable across switches
    double maxExtent = 120.0;
    for (final s in allStrokes) {
      for (final pt in s.smoothPoints) {
        maxExtent = math.max(maxExtent, pt.dx.abs());
        maxExtent = math.max(maxExtent, pt.dy.abs());
      }
    }
    // Add 25% padding
    maxExtent *= 1.25;

    // Scale factor to map relative pixels into canvas
    final scale = math.min(size.width, size.height) / (2.0 * maxExtent);

    // Transform relative offset (where +X is forward, +Y is upward) to screen coordinates
    Offset toScreen(Offset relative) {
      return Offset(
        center.dx + relative.dx * scale,
        center.dy - relative.dy * scale, // invert screen Y so +Y is up
      );
    }

    // 1. Draw Background Grid & Axis Lines
    _drawGridAndAxes(canvas, size, center, scale, maxExtent);

    // 2. Draw Raw Points (if enabled)
    if (showRawPoints && stroke.rawPoints.isNotEmpty) {
      final rawPaint = Paint()
        ..color = Colors.white.withOpacity(0.2)
        ..style = PaintingStyle.fill;

      final rawLinePaint = Paint()
        ..color = Colors.white.withOpacity(0.12)
        ..strokeWidth = 1.0
        ..style = PaintingStyle.stroke;

      final rawPath = Path();
      for (int i = 0; i < stroke.rawPoints.length; i++) {
        final screenPt = toScreen(stroke.rawPoints[i]);
        if (i == 0) {
          rawPath.moveTo(screenPt.dx, screenPt.dy);
        } else {
          rawPath.lineTo(screenPt.dx, screenPt.dy);
        }
        canvas.drawCircle(screenPt, 2.0, rawPaint);
      }
      canvas.drawPath(rawPath, rawLinePaint);
    }

    // 3. Draw 100-Point Smoothed Trajectory Path
    if (stroke.smoothPoints.isNotEmpty) {
      final path = Path();
      final screenStart = toScreen(stroke.smoothPoints.first);
      path.moveTo(screenStart.dx, screenStart.dy);

      for (int i = 1; i < stroke.smoothPoints.length; i++) {
        final screenPt = toScreen(stroke.smoothPoints[i]);
        path.lineTo(screenPt.dx, screenPt.dy);
      }

      // Trajectory Glow
      final glowPaint = Paint()
        ..color = const Color(0xFF00B0FF).withOpacity(0.25)
        ..strokeWidth = 8.0
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..style = PaintingStyle.stroke;
      canvas.drawPath(path, glowPaint);

      // Trajectory Main Line
      final mainPaint = Paint()
        ..color = const Color(0xFF00B0FF)
        ..strokeWidth = 3.5
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..style = PaintingStyle.stroke;
      canvas.drawPath(path, mainPaint);
    }

    // 4. Draw Start & End Markers
    if (stroke.smoothPoints.isNotEmpty) {
      final startScreen = toScreen(stroke.smoothPoints.first);
      final endScreen = toScreen(stroke.smoothPoints.last);

      // Start Marker (Green Circle)
      final startGlow = Paint()..color = const Color(0xFF00E676).withOpacity(0.3);
      canvas.drawCircle(startScreen, 9, startGlow);
      final startPaint = Paint()..color = const Color(0xFF00E676);
      canvas.drawCircle(startScreen, 5, startPaint);
      _drawText(canvas, 'Start', startScreen + const Offset(8, -8), const Color(0xFF00E676));

      // End Marker (Purple Square)
      final endPaint = Paint()..color = const Color(0xFFE040FB);
      canvas.drawRect(Rect.fromCenter(center: endScreen, width: 9, height: 9), endPaint);
      _drawText(canvas, 'End', endScreen + const Offset(8, -8), const Color(0xFFE040FB));
    }

    // 5. Draw Live Video Playback Bead (Real-time tracking along the stroke curve!)
    if (progressRatio != null && stroke.smoothPoints.isNotEmpty) {
      final clampedRatio = progressRatio!.clamp(0.0, 1.0);
      final targetIdx = ((stroke.smoothPoints.length - 1) * clampedRatio).round();
      final currentPt = toScreen(stroke.smoothPoints[targetIdx]);

      // Pulsing glow
      final beadGlow = Paint()..color = Colors.amberAccent.withOpacity(0.5);
      canvas.drawCircle(currentPt, 12, beadGlow);

      final beadPaint = Paint()..color = Colors.amberAccent;
      canvas.drawCircle(currentPt, 6, beadPaint);

      final beadCenter = Paint()..color = Colors.white;
      canvas.drawCircle(currentPt, 2.5, beadCenter);

      _drawText(canvas, 'Current', currentPt + const Offset(10, 4), Colors.amberAccent, isBold: true);
    }

    // 6. Draw Fixed Shoulder (0, 0) Origin at Dead Center
    _drawShoulderOrigin(canvas, center);
  }

  void _drawGridAndAxes(Canvas canvas, Size size, Offset center, double scale, double maxExtent) {
    final gridPaint = Paint()
      ..color = Colors.white.withOpacity(0.06)
      ..strokeWidth = 0.8;

    final axisPaint = Paint()
      ..color = Colors.white.withOpacity(0.25)
      ..strokeWidth = 1.5;

    // Draw concentric circles / grid steps around (0, 0)
    final stepPx = 30.0; // 30 pixels interval in swim space
    for (double r = stepPx; r < maxExtent; r += stepPx) {
      final screenRadius = r * scale;
      canvas.drawCircle(center, screenRadius, gridPaint);
      // Distance label on X axis
      _drawText(
        canvas,
        '${r.toInt()}',
        Offset(center.dx + screenRadius, center.dy + 4),
        Colors.white24,
        fontSize: 10,
      );
    }

    // Draw Major Crosshair Axes through Center
    canvas.drawLine(Offset(0, center.dy), Offset(size.width, center.dy), axisPaint);
    canvas.drawLine(Offset(center.dx, 0), Offset(center.dx, size.height), axisPaint);

    // Directional Labels
    _drawText(canvas, '+X 前伸 (Forward)', Offset(size.width - 120, center.dy - 18), Colors.cyanAccent.withOpacity(0.8), fontSize: 11);
    _drawText(canvas, '-X 後推 (Backward)', Offset(10, center.dy - 18), Colors.white54, fontSize: 11);
    _drawText(canvas, '+Y 水面 (Surface)', Offset(center.dx + 8, 10), Colors.lightBlueAccent.withOpacity(0.8), fontSize: 11);
    _drawText(canvas, '-Y 水深 (Depth)', Offset(center.dx + 8, size.height - 24), Colors.blueGrey.withOpacity(0.8), fontSize: 11);
  }

  void _drawShoulderOrigin(Canvas canvas, Offset center) {
    final shoulderPaint = Paint()
      ..color = const Color(0xFFFF5252)
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;

    final crossSize = 9.0;
    canvas.drawLine(
      Offset(center.dx - crossSize, center.dy),
      Offset(center.dx + crossSize, center.dy),
      shoulderPaint,
    );
    canvas.drawLine(
      Offset(center.dx, center.dy - crossSize),
      Offset(center.dx, center.dy + crossSize),
      shoulderPaint,
    );

    // Concentric ring
    final ringPaint = Paint()
      ..color = const Color(0xFFFF5252).withOpacity(0.4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawCircle(center, 6.0, ringPaint);

    _drawText(
      canvas,
      '肩膀 Shoulder (0, 0)',
      Offset(center.dx + 10, center.dy + 8),
      const Color(0xFFFF5252),
      isBold: true,
      fontSize: 11,
    );
  }

  void _drawText(Canvas canvas, String text, Offset position, Color color, {double fontSize = 11, bool isBold = false}) {
    final textSpan = TextSpan(
      text: text,
      style: TextStyle(
        color: color,
        fontSize: fontSize,
        fontWeight: isBold ? FontWeight.bold : FontWeight.w500,
        fontFamily: 'Roboto',
      ),
    );
    final textPainter = TextPainter(
      text: textSpan,
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(canvas, position);
  }

  @override
  bool shouldRepaint(covariant _TrajectoryPainter oldDelegate) {
    return oldDelegate.stroke != stroke ||
        oldDelegate.showRawPoints != showRawPoints ||
        oldDelegate.progressRatio != progressRatio;
  }
}
