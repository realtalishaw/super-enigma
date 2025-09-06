# 🚀 Quick Start: Streamlit Evals Frontend

A beautiful web interface for running and analyzing workflow automation evaluations.

## 🎯 What You Get

- **📊 Time-Series Dashboard**: Track performance trends over time on the homepage
- **🤖 AI Analysis**: Intelligent insights and improvement recommendations
- **📈 API Usage Tracking**: Monitor catalog and suggestions endpoint usage
- **🔄 Real-Time Progress**: See evaluation results as they complete, not just at the end
- **📈 Interactive Charts**: Rich visualizations with hover details and zoom
- **📋 Historical Reports**: Browse and compare past evaluation runs
- **🔧 Test Case Management**: Add, edit, and manage evaluation test cases
- **⚡ Quick Actions**: Run evaluations directly from the dashboard
- **🔄 Dual Mode Support**: Run evaluations locally or via API

## ⚡ Quick Launch

### Option 1: Demo Script (Recommended)
```bash
python evals/demo_frontend.py
```

### Option 2: Direct Launch
```bash
python evals/run_streamlit.py
```

### Option 3: Manual Launch
```bash
streamlit run evals/streamlit_app.py
```

The dashboard will open at: **http://localhost:8501**

## 🔧 Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables** (for local evaluations):
   ```bash
   # In your .env file
   ANTHROPIC_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here
   ```

3. **API Server** (for API-based evaluations):
   ```bash
   # Start your API server
   python api/run.py
   ```

## 📊 Dashboard Features

### 1. Dashboard (Homepage)
- **Overall Performance Summary**: Average metrics across all evaluation runs
- **Time-Series Charts**: Performance trends over time
- **Recent Reports Table**: Last 10 evaluation runs
- **AI Analysis**: Intelligent insights and improvement recommendations
- **Quick Actions**: Run evaluations, view reports, manage test cases

### 2. Run New Evaluation
- **Real-Time Progress**: See results as they complete
- **Live Metrics**: Pass rate, latency, accuracy updates
- **Case-by-Case Updates**: Each test case result shown immediately
- **Local/API Mode**: Direct service or HTTP API calls
- **Test Case Selection**: Choose specific cases or run all

### 3. View Reports
- **Historical Data**: Browse all past evaluation runs
- **Interactive Charts**: Latency, accuracy, pass/fail distribution
- **Report Comparison**: Compare performance across runs
- **Export Data**: Download reports as JSON

### 4. API Usage & Testing
- **User-Friendly API Tester**: Swagger UI-like interface for testing all endpoints
- **Parameter Support**: Full parameter input for all endpoints (search, filters, pagination)
- **Real-Time Monitoring**: Track API endpoint usage and performance
- **Live API Testing**: Test all catalog, integrations, and suggestions endpoints
- **Usage Statistics**: Request counts, response times, success rates
- **Endpoint Analysis**: Detailed breakdown by integrations and suggestions endpoints
- **Time Series Charts**: Request volume over time
- **API Health**: Connection status and performance metrics

### 5. Manage Test Cases
- **Table View**: All test cases in a clean table
- **Add New Cases**: Create custom test scenarios
- **Edit Existing**: Modify test case parameters
- **Validation**: Ensure proper test case structure

### 6. Settings
- **Environment Status**: Check API keys and configuration
- **API Configuration**: Set server URLs and ports
- **System Info**: Version and dependency information

## 📈 Available Visualizations

- **Time-Series Charts**: Performance trends over time
  - Pass Rate Over Time
  - Average Latency Over Time
  - Average Accuracy Over Time
- **Real-Time Charts**: Live updates during evaluation runs
- **Individual Report Charts**: 
  - Latency Chart: Response time per test case
  - Accuracy Chart: Accuracy scores across test cases
  - Pass/Fail Pie Chart: Success rate visualization
- **Summary Metrics**: Key performance indicators
- **Detailed Results**: Per-test case analysis

## 🎨 Sample Workflow

1. **Launch Dashboard**:
   ```bash
   python evals/demo_frontend.py
   ```

2. **Run Evaluation**:
   - Go to "Run New Evaluation"
   - Select "API-based" (if API server is running)
   - Choose test cases to run
   - Click "Run Evaluation"

3. **View Results**:
   - Explore interactive charts
   - Check detailed per-test results
   - Review summary metrics

4. **Manage Test Cases**:
   - Go to "Manage Test Cases"
   - Add new test scenarios
   - Edit existing cases

## 🔍 Troubleshooting

### Common Issues

**Streamlit not found**:
```bash
pip install streamlit plotly pandas
```

**Missing environment variables**:
- Check your `.env` file
- Ensure API keys are properly set

**API connection failed**:
- Make sure API server is running
- Check port configuration (default: 8001)

**No test cases found**:
- Verify `eval_prompts.json` exists
- Check JSON file format

### Environment Setup

**For Local Evaluations**:
- Set `ANTHROPIC_API_KEY` and `GROQ_API_KEY`
- Ensure DSL generator service can be imported
- Configure database connections

**For API Evaluations**:
- Start API server: `python api/run.py`
- Verify API is accessible at configured port
- Check authentication if required

## 📁 File Structure

```
evals/
├── streamlit_app.py          # Main Streamlit application
├── run_streamlit.py          # Launcher script
├── demo_frontend.py          # Demo and setup script
├── test_streamlit_app.py     # Test suite
├── run_evals.py              # Local evaluation runner
├── run_evals_api.py          # API-based evaluation runner
├── eval_prompts.json         # Test case definitions
├── *.json                    # Historical evaluation reports
├── README_STREAMLIT.md       # Detailed documentation
└── QUICK_START_FRONTEND.md   # This file
```

## 🚀 Advanced Usage

### Custom Test Cases
Add new test cases through the web interface or directly edit `eval_prompts.json`:

```json
{
  "id": "CUSTOM_CASE_001",
  "prompt": "Your test prompt here",
  "selected_apps": ["app1", "app2"],
  "expected": {
    "apps": ["app1", "app2"],
    "trigger_slug": "EXPECTED_TRIGGER",
    "action_slugs": ["EXPECTED_ACTION"],
    "min_steps": 1
  }
}
```

### API Integration
The frontend supports both local and API-based evaluation modes:

- **Local Mode**: Direct service integration, requires full environment setup
- **API Mode**: HTTP API calls, requires running API server

### Custom Visualizations
Extend the dashboard with new chart types by modifying the visualization functions in `streamlit_app.py`.

## 🎉 Success!

You now have a fully functional web interface for your workflow automation evaluations! The dashboard provides:

- ✅ Easy evaluation execution
- ✅ Rich data visualization
- ✅ Historical report analysis
- ✅ Test case management
- ✅ Real-time progress tracking

**Happy Evaluating!** 🚀
