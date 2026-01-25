import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models.dart';

class AnalysisChartWidget extends StatefulWidget {
  final InteractivePlot plotData;
  final ValueNotifier<double>? currentTimeNotifier;
  final Color lineColor;
  final Function(double startS, double endS)? onPhaseTap;

  const AnalysisChartWidget({
    Key? key,
    required this.plotData,
    this.lineColor = Colors.blueAccent,
    this.onPhaseTap,
    this.currentTimeNotifier,
  }) : super(key: key);

  @override
  _AnalysisChartWidgetState createState() => _AnalysisChartWidgetState();
}

class _AnalysisChartWidgetState extends State<AnalysisChartWidget> {
  double? _hoverX;
  bool _highlightAllMinima = false;

  @override
  Widget build(BuildContext context) {
    if (widget.plotData.dataPoints.isEmpty) {
      return Center(child: Text('No data for ${widget.plotData.title}'));
    }

    // Identify Chart Type
    final isKickAngle = widget.plotData.title.contains("Kick Angle") || widget.plotData.plotType == 'angle';

    // 0. Check Flip Condition (Metadata or Legacy Title check)
    bool isFlipped = false;
    if (widget.plotData.timeSeries != null && 
        widget.plotData.timeSeries!['metadata'] != null &&
        widget.plotData.timeSeries!['metadata']['reverse_axis'] != null) {
      isFlipped = widget.plotData.timeSeries!['metadata']['reverse_axis'];
    } else {
      final t = widget.plotData.title.toLowerCase();
      isFlipped = t.contains("range1") || t.contains("decreasing") || t.contains("left");
    }
    
    // Calculate global bounds first to support flipping
    double dataMinTime = 0;
    double dataMaxTime = 0;
    if (widget.plotData.dataPoints.isNotEmpty) {
      dataMinTime = widget.plotData.dataPoints.first.timestampMs / 1000.0;
      dataMaxTime = widget.plotData.dataPoints.last.timestampMs / 1000.0;
    }
    
    // Transform function
    double getX(double t) {
      if (isFlipped) {
        return dataMaxTime - (t - dataMinTime); 
      }
      return t;
    }
    // Reverse Transform function (for interactions)
    double getTime(double x) {
      if (isFlipped) {
        return dataMinTime + (dataMaxTime - x);
      }
      return x;
    }

    // 1. Process Data & Regions
    final List<FlSpot> spots = [];
    final List<VerticalRangeAnnotation> phaseRegions = [];
    final Set<String> presentPhases = {}; // Track present phases for legend

    String? currentPhase;
    double? startT; // Change from startX to startT (Time)

    // Map of Phase -> Color
    final Map<String, Color> phaseColors = {
      "Glide": Colors.grey.withOpacity(0.1),
      "Pull": Colors.blue.withOpacity(0.2),
      "Push": Colors.orange.withOpacity(0.2),
      "Recovery": Colors.green.withOpacity(0.2),
    };

    // Highlight Colors (more opaque/vivid)
    final Map<String, Color> highlightColors = {
      "Pull": Colors.blue.withOpacity(0.5),
      "Push": Colors.orange.withOpacity(0.5),
      "Recovery": Colors.green.withOpacity(0.5),
      "Glide": Colors.grey.withOpacity(0.4),
    };

    for (var i = 0; i < widget.plotData.dataPoints.length; i++) {
      final p = widget.plotData.dataPoints[i];
      final t = p.timestampMs / 1000.0;
      final x = getX(t);
      spots.add(FlSpot(x, p.value));

      // Region Detection
      final phase = p.phase ?? "Glide";
      presentPhases.add(phase);

      if (phase != currentPhase) {
        // Close previous region
        if (currentPhase != null && startT != null) {
          final endT = t;
          final x1 = getX(startT);
          final x2 = x; 
          double sx = x1 < x2 ? x1 : x2;
          double ex = x1 < x2 ? x2 : x1;

          bool isHovered = false;
          if (_hoverX != null && sx <= _hoverX! && ex >= _hoverX!) {
            isHovered = true;
          }
          
          phaseRegions.add(VerticalRangeAnnotation(
            x1: sx,
            x2: ex,
            color: isHovered 
                ? (highlightColors[currentPhase] ?? Colors.transparent) 
                : (phaseColors[currentPhase] ?? Colors.transparent),
          ));
        }
        // Start new region
        currentPhase = phase;
        startT = t;
      }
    }
    // Close last region
    if (currentPhase != null && startT != null) {
       bool isHovered = false;
       final lastT = widget.plotData.dataPoints.last.timestampMs / 1000.0;
       final x1 = getX(startT);
       final x2 = getX(lastT);
       double sx = x1 < x2 ? x1 : x2;
       double ex = x1 < x2 ? x2 : x1;

       if (_hoverX != null && sx <= _hoverX! && ex >= _hoverX!) {
         isHovered = true;
       }

       phaseRegions.add(VerticalRangeAnnotation(
          x1: sx,
          x2: ex,
          color: isHovered 
              ? (highlightColors[currentPhase] ?? Colors.transparent)
              : (phaseColors[currentPhase] ?? Colors.transparent),
       ));
    }

    // 2. Extract Minima for Highlighting
    final List<int> minimaIndices = [];
    final List<FlSpot> minimaSpots = [];

    if (widget.plotData.timeSeries != null &&
        widget.plotData.timeSeries!['metadata'] != null &&
        widget.plotData.timeSeries!['metadata']['minima'] != null) {
      
      print("DEBUG-FRONTEND: Metadata Keys: ${widget.plotData.timeSeries!['metadata'].keys.toList()}");
      print("DEBUG-FRONTEND: Full Metadata: ${widget.plotData.timeSeries!['metadata']}");
      print("DEBUG-FRONTEND: Metadata Segment Metrics: ${widget.plotData.timeSeries!['metadata']['segment_metrics']}");

      final minimaList = widget.plotData.timeSeries!['metadata']['minima'] as List;
      for (var m in minimaList) {
         final mFrame = m['frame'];
         final index = widget.plotData.dataPoints.indexWhere((dp) => dp.frame == mFrame);

         if (index != -1) {
           minimaIndices.add(index);
           minimaSpots.add(spots[index]); 
         }
      }
    }

    double minY = spots.map((e) => e.y).reduce((a, b) => a < b ? a : b);
    double maxY = spots.map((e) => e.y).reduce((a, b) => a > b ? a : b);

    // 3. Extract Segment Metrics (Top Labels)
    final List<FlSpot> metricSpots = [];
    final List<String> metricLabels = [];
    final List<int> metricIndices = [];

    if (widget.plotData.timeSeries != null &&
        widget.plotData.timeSeries!['metadata'] != null &&
        widget.plotData.timeSeries!['metadata']['segment_metrics'] != null) {

      final metricsList = widget.plotData.timeSeries!['metadata']['segment_metrics'] as List;
      int mIndex = 0;
      for (var m in metricsList) {
         final centerF = (m['center_frame'] as num).toDouble();
         final label = m['label'] as String;

         final dp = widget.plotData.dataPoints.firstWhere(
           (d) => d.frame >= centerF,
           orElse: () => widget.plotData.dataPoints.last
         );

         double t = dp.timestampMs / 1000.0;
         double x = getX(t);
         
         metricSpots.add(FlSpot(x, maxY)); 
         metricLabels.add(label);
         metricIndices.add(mIndex);
         mIndex++;
      }
    }
    
    // Add extra padding for top labels
    double yRange = maxY - minY;
    if (yRange == 0) yRange = 1;
    minY -= yRange * 0.1;
    maxY += yRange * 0.4; // Increased padding to prevent label clipping 
    
    // Sort spots by X to ensuring correct rendering for fl_chart
    spots.sort((a, b) => a.x.compareTo(b.x));

    // Re-calculate X bounds based on spots (visual X)
    double minX = spots.map((e) => e.x).reduce((a, b) => a < b ? a : b);
    double maxX = spots.map((e) => e.x).reduce((a, b) => a > b ? a : b);

    // Build the Chart with ValueListenableBuilder for animation
    return ValueListenableBuilder<double>(
      valueListenable: widget.currentTimeNotifier ?? ValueNotifier(-1.0),
      builder: (context, currentTime, child) {
        // Calculate Gradient Progress (normX)
        // normX represents the cut-off point on the X-axis (0.0 to 1.0)
        double normX = 0.0;
        
        if (currentTime < 0) {
           // Not playing -> Show full Light (or Full Dark? Usually full light "Ghost")
           // If we want "start as ghost", then Normal: stops=[0,0,0,1] (All Light)
           // Flipped: stops=[0,1,1,1]? (All Light)
           // Let's rely on data ranges.
           if (isFlipped) normX = 1.0; // All Light (Left->Right: Light...Light|Dark) -> Wait, Flipped: Light->Dark. If normX=1, Left->Right is Light.
           else normX = 0.0; // All Light (Left->Right: Dark|Light...Light). If normX=0, all Light.
        } else {
           double currentX = getX(currentTime);
           // Clamp X to bounds
           if (currentX < minX) currentX = minX;
           if (currentX > maxX) currentX = maxX;
           
           if (maxX != minX) {
              normX = (currentX - minX) / (maxX - minX);
           }
        }
        
        // Define Gradient Colors & Stops
        Color lightColor = widget.lineColor.withOpacity(0.3);
        Color darkColor = widget.lineColor;
        
        List<Color> gradientColors;
        List<double> gradientStops;
        
        // Ensure epsilon for sharp transition
        const double epsilon = 0.0001;
        double stop1 = normX - epsilon;
        double stop2 = normX + epsilon;
        if (stop1 < 0) stop1 = 0;
        if (stop2 > 1) stop2 = 1;

        if (isFlipped) {
           // Flipped (Time increases Right -> Left)
           // Active Region (Past) is Right side (X > currentX, i.e., Normalized > normX)
           // Gradient (Left -> Right): Future (Light) -> Past (Dark)
           gradientColors = [lightColor, lightColor, darkColor, darkColor];
           gradientStops = [0.0, stop1, stop2, 1.0];
        } else {
           // Normal (Time increases Left -> Right)
           // Active Region (Past) is Left side (X < currentX, i.e., Normalized < normX)
           // Gradient (Left -> Right): Past (Dark) -> Future (Light)
           gradientColors = [darkColor, darkColor, lightColor, lightColor];
           gradientStops = [0.0, stop1, stop2, 1.0];
        }

        // Single Line with Gradient
        final barData = LineChartBarData(
          spots: spots, // Always full spots, no jitter!
          isCurved: true,
          preventCurveOverShooting: true,
          gradient: LinearGradient(
             colors: gradientColors,
             stops: gradientStops,
             begin: Alignment.centerLeft,
             end: Alignment.centerRight,
          ),
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: FlDotData(show: false),
        );

        final barData1 = LineChartBarData(
          spots: minimaSpots,
          isCurved: false,
          color: Colors.red,
          barWidth: 0,
          dotData: FlDotData(
            show: true,
            getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(
              radius: 4, color: Colors.red, strokeWidth: 1, strokeColor: Colors.white
            )
          ),
        );

        final barData2 = LineChartBarData(
          spots: metricSpots,
          isCurved: false,
          color: Colors.transparent,
          barWidth: 0,
          dotData: FlDotData(
            show: true, 
            getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(radius: 0, color: Colors.transparent)
          ),
        );

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Legend
                Row(
                  children: isKickAngle
                      ? [
                          // Kick Angle: Show "MIN ANGLE" with Red Dot
                          Padding(
                            padding: EdgeInsets.only(left: 8),
                            child: Row(children: [
                               Container(
                                 width: 10, height: 10, 
                                 decoration: BoxDecoration(color: Colors.red, shape: BoxShape.circle)
                               ),
                               SizedBox(width: 4),
                               Text("MIN ANGLE", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                            ]),
                          )
                        ]
                      : 
                      // Stroke Chart: Show detected phases
                      phaseColors.entries
                          .where((e) => presentPhases.contains(e.key))
                          .map((e) => Padding(
                            padding: EdgeInsets.only(left: 8),
                            child: Row(children: [
                               Container(width: 10, height: 10, color: e.value.withOpacity(1.0)),
                               SizedBox(width: 4),
                               Text(e.key, style: TextStyle(fontSize: 10)),
                            ]),
                          )).toList(),
                )
              ],
            ),
            SizedBox(height: 16),
            Expanded(
              child: Padding(
                padding: EdgeInsets.only(right: 16),
                child: LineChart(
                  LineChartData(
                    lineTouchData: LineTouchData(
                      enabled: true,
                      mouseCursorResolver: (event, response) {
                        if (response == null || response.lineBarSpots == null) {
                          return SystemMouseCursors.basic;
                        }
                        return SystemMouseCursors.click;
                      },
                      touchCallback: (FlTouchEvent event, LineTouchResponse? touchResponse) {
                        if (event is FlPanEndEvent || event is FlLongPressEnd || touchResponse == null || touchResponse.lineBarSpots == null) {
                          setState(() {
                             _hoverX = null;
                             _highlightAllMinima = false;
                          });
                        } else {
                          if (touchResponse.lineBarSpots!.isNotEmpty) {
                            final x = touchResponse.lineBarSpots!.first.x;
                            
                            // Check if hitting a Minima (Checking proximity to ANY minima spot)
                            bool hitMinima = false;
                            for (var mSpot in minimaSpots) {
                              if ((mSpot.x - x).abs() < 0.1) { // Threshold: 0.1s
                                 hitMinima = true;
                                 break;
                              }
                            }

                            setState(() {
                               _hoverX = x;
                               _highlightAllMinima = hitMinima; 
                            });
                            
                            // Handle Tap for Replay
                            if (event is FlTapUpEvent) {
                               for (var pr in phaseRegions) {
                                  if (x >= pr.x1 && x <= pr.x2) {
                                    double t1 = getTime(pr.x1);
                                    double t2 = getTime(pr.x2);
                                    double startS = t1 < t2 ? t1 : t2;
                                    double endS = t1 < t2 ? t2 : t1;
                                    widget.onPhaseTap?.call(startS, endS);
                                    break;
                                  }
                               }
                            }
                          }
                        }
                      },
                      touchTooltipData: LineTouchTooltipData(
                        tooltipBgColor: Colors.transparent, // Transparent for permanent labels
                        tooltipPadding: const EdgeInsets.all(0),
                        tooltipMargin: 8,
                        getTooltipItems: (touchedSpots) {
                          return touchedSpots.map((LineBarSpot touchedSpot) {
                            // 1. Minima (Index 1)
                            if (touchedSpot.barIndex == 1) {
                               return LineTooltipItem(
                                 touchedSpot.y.toStringAsFixed(1),
                                 const TextStyle(color: Colors.red, fontWeight: FontWeight.bold, fontSize: 12),
                               );
                            }

                            if (touchedSpot.barIndex == 2) { // Metrics (Index 2)
                               final index = touchedSpot.spotIndex;
                               if (index < metricLabels.length) {
                                 return LineTooltipItem(
                                   metricLabels[index],
                                   const TextStyle(color: Colors.green, fontWeight: FontWeight.bold, fontSize: 12),
                                 );
                               }
                               return null;
                            }

                            // 2. Main Waveform (Index 0)
                            if (touchedSpot.barIndex == 0) {
                               final visualX = touchedSpot.x;
                               final t = getTime(visualX);
                               
                               final p = widget.plotData.dataPoints.firstWhere(
                                 (dp) => (dp.timestampMs / 1000.0 - t).abs() < 0.05, 
                                 orElse: () => widget.plotData.dataPoints.first,
                               );

                               return LineTooltipItem(
                                 "${p.phase ?? 'Val'}\n",
                                 const TextStyle(color: Colors.blueGrey, fontWeight: FontWeight.bold),
                                 children: [
                                   TextSpan(
                                     text: "${touchedSpot.y.toStringAsFixed(1)}",
                                     style: TextStyle(color: Colors.black, fontWeight: FontWeight.normal)
                                   )
                                 ]
                               );
                            }
                            return null;
                          }).toList();
                        }
                      )
                    ),
                    showingTooltipIndicators: [
                      if (_highlightAllMinima) 
                        ...List.generate(minimaSpots.length, (index) {
                           return ShowingTooltipIndicators([
                             LineBarSpot(
                               barData1, // Minima Bar
                               1, // Index in list
                               minimaSpots[index]
                             ),
                           ]);
                        }),
                      ...List.generate(metricSpots.length, (index) {
                         return ShowingTooltipIndicators([
                           LineBarSpot(
                             barData2, // Metrics Bar
                             2, // Index in list
                             metricSpots[index]
                           ),
                         ]);
                      }),
                    ],
                    rangeAnnotations: RangeAnnotations(verticalRangeAnnotations: phaseRegions),
                    gridData: FlGridData(show: true, drawVerticalLine: false),
                    titlesData: FlTitlesData(
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 22,
                          interval: (maxX - minX) > 10 ? (maxX - minX) / 5 : 1,
                          getTitlesWidget: (value, meta) {
                            if (value < minX || value > maxX) return SizedBox.shrink();
                            double t = getTime(value);
                            return Text('${t.toStringAsFixed(1)}s', style: TextStyle(fontSize: 10));
                          },
                        ),
                      ),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 40,
                          getTitlesWidget: (value, meta) {
                            return Text(value.toStringAsFixed(1), style: TextStyle(fontSize: 10));
                          },
                        ),
                      ),
                      topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    ),
                    borderData: FlBorderData(show: true, border: Border.all(color: Colors.black12)),
                    minX: minX,
                    maxX: maxX,
                    minY: minY,
                    maxY: maxY,
                    lineBarsData: [
                      barData, // Index 0
                      barData1, // Minima Index 1
                      barData2, // Metrics Index 2
                    ],
                  ),
                ),
              ),
            ),
          ],
        );
      }
    );
  }
}
