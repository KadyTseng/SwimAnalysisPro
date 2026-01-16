import 'dart:async';
import 'package:flutter/material.dart';
import '../api_service.dart';
import '../models.dart';
import 'result_screen.dart';

class AnalysisProgressScreen extends StatefulWidget {
  final String videoId;

  const AnalysisProgressScreen({Key? key, required this.videoId}) : super(key: key);

  @override
  _AnalysisProgressScreenState createState() => _AnalysisProgressScreenState();
}

class _AnalysisProgressScreenState extends State<AnalysisProgressScreen> {
  final ApiService _apiService = ApiService();
  Timer? _timer;
  double _progress = 0.0;
  String _statusMessage = 'Initializing...';
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _timer = Timer.periodic(Duration(seconds: 2), (timer) async {
      try {
        final statusResponse = await _apiService.checkStatus(widget.videoId);
        
        if (mounted) {
          setState(() {
            _progress = (statusResponse.progress ?? 0) / 100.0;
            _statusMessage = 'Status: ${statusResponse.status}\nProgress: ${(statusResponse.progress ?? 0)}%';
          });
        }

        if (statusResponse.status == 'completed') {
          timer.cancel();
          _fetchAndNavigateToResult();
        } else if (statusResponse.status == 'failed') {
          timer.cancel();
          setState(() {
            _hasError = true;
            _statusMessage = 'Analysis Failed: ${statusResponse.errorMessage}';
          });
        }
      } catch (e) {
        print('Polling error: $e');
      }
    });
  }

  Future<void> _fetchAndNavigateToResult() async {
    try {
      final result = await _apiService.getResult(widget.videoId);
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (context) => ResultScreen(result: result),
          ),
        );
      }
    } catch (e) {
      setState(() {
        _hasError = true;
        _statusMessage = 'Failed to fetch results: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Analyzing...')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (!_hasError) ...[
                CircularProgressIndicator(value: _progress > 0 ? _progress : null),
                SizedBox(height: 24),
                Text(
                  '${(_progress * 100).toInt()}%',
                  style: Theme.of(context).textTheme.displayMedium,
                ),
                SizedBox(height: 16),
              ],
              Icon(
                _hasError ? Icons.error_outline : Icons.auto_awesome,
                size: 64,
                color: _hasError ? Colors.red : Colors.blueAccent,
              ),
              SizedBox(height: 24),
              Text(
                _statusMessage,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 18, 
                  color: _hasError ? Colors.red : Colors.black87
                ),
              ),
              if (_hasError) ...[
                SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text('Go Back'),
                )
              ]
            ],
          ),
        ),
      ),
    );
  }
}
