import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models.dart';

class AnalysisChartWidget extends StatelessWidget {
  final InteractivePlot plotData;
  final Color lineColor;

  const AnalysisChartWidget({
    Key? key, 
    required this.plotData,
    this.lineColor = Colors.blueAccent,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    if (plotData.dataPoints.isEmpty) {
      return Center(child: Text('No data for ${plotData.title}'));
    }

    // 1. Process Data & Regions
    final List<FlSpot> spots = [];
    final List<VerticalRangeAnnotation> phaseRegions = [];
    
    String? currentPhase;
    double? startX;
    
    // Map of Phase -> Color
    final Map<String, Color> phaseColors = {
      "Pull": Colors.blue.withOpacity(0.2),
      "Push": Colors.orange.withOpacity(0.2),
      "Recovery": Colors.green.withOpacity(0.2),
      "Glide/Other": Colors.grey.withOpacity(0.1),
    };

    for (var i = 0; i < plotData.dataPoints.length; i++) {
      final p = plotData.dataPoints[i];
      final x = p.timestampMs / 1000.0;
      spots.add(FlSpot(x, p.value));

      // Region Detection
      final phase = p.phase ?? "Glide/Other";
      if (phase != currentPhase) {
        // Close previous region
        if (currentPhase != null && startX != null) {
          phaseRegions.add(VerticalRangeAnnotation(
            x1: startX,
            x2: x,
            color: phaseColors[currentPhase] ?? Colors.transparent,
          ));
        }
        // Start new region
        currentPhase = phase;
        startX = x;
      }
    }
    // Close last region
    if (currentPhase != null && startX != null) {
       phaseRegions.add(VerticalRangeAnnotation(
          x1: startX,
          x2: spots.last.x,
          color: phaseColors[currentPhase] ?? Colors.transparent,
       ));
    }
    
    // Debug Log
    if (phaseRegions.isNotEmpty) {
       print("[ChartWidget: ${plotData.title}] Generated ${phaseRegions.length} Phase Regions.");
    } else {
       print("[ChartWidget: ${plotData.title}] No Phase Regions detected (all maybe 'Glide/Other').");
    }

    double maxX = spots.last.x;
    double minX = spots.first.x;
    double minY = spots.map((e) => e.y).reduce((a, b) => a < b ? a : b);
    double maxY = spots.map((e) => e.y).reduce((a, b) => a > b ? a : b);
    
    double yRange = maxY - minY;
    if (yRange == 0) yRange = 1;
    minY -= yRange * 0.1;
    maxY += yRange * 0.1;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(plotData.title, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            // Legend
            Row(
              children: phaseColors.entries.where((e) => e.key != "Glide/Other").map((e) => Padding(
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
                  touchTooltipData: LineTouchTooltipData(
                    getTooltipItems: (touchedSpots) {
                      return touchedSpots.map((LineBarSpot touchedSpot) {
                        // Find original point to get Phase info
                        final p = plotData.dataPoints.firstWhere(
                          (dp) => (dp.timestampMs / 1000.0 - touchedSpot.x).abs() < 0.001,
                          orElse: () => plotData.dataPoints.first, 
                        );
                        
                        return LineTooltipItem(
                          "${p.phase ?? 'Unknown'}\n",
                          const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          children: [
                            TextSpan(
                              text: "${touchedSpot.x.toStringAsFixed(2)}s\nVal: ${touchedSpot.y.toStringAsFixed(2)}",
                              style: TextStyle(color: Colors.yellowAccent, fontWeight: FontWeight.normal)
                            )
                          ]
                        );
                      }).toList();
                    }
                  )
                ),
                rangeAnnotations: RangeAnnotations(verticalRangeAnnotations: phaseRegions),
                gridData: FlGridData(show: true, drawVerticalLine: false),
                titlesData: FlTitlesData(
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 22,
                      interval: (maxX - minX) > 10 ? (maxX - minX) / 5 : 1, // Adjusted interval logic
                      getTitlesWidget: (value, meta) {
                        if (value < minX || value > maxX) return SizedBox.shrink();
                        return Text('${value.toStringAsFixed(1)}s', style: TextStyle(fontSize: 10));
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
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    color: lineColor,
                    barWidth: 3,
                    isStrokeCapRound: true,
                    dotData: FlDotData(show: false),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
