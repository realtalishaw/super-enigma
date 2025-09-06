# Streamlit Evals Dashboard

A web-based frontend for the Workflow Automation Engine evaluation system, built with Streamlit.

## Features

- **Run Evaluations**: Execute evaluations locally or via API
- **View Results**: Interactive charts and detailed result analysis
- **Historical Reports**: Browse and compare past evaluation runs
- **Test Case Management**: Add, edit, and manage evaluation test cases
- **Real-time Metrics**: Live performance and accuracy metrics

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Make sure your `.env` file contains the required API keys:

```bash
ANTHROPIC_API_KEY=your_anthropic_key
GROQ_API_KEY=your_groq_key
API_PORT=8001  # Optional, defaults to 8001
```

### 3. Launch the Dashboard

```bash
# From the project root
python evals/run_streamlit.py

# Or directly with streamlit
streamlit run evals/streamlit_app.py
```

The dashboard will be available at: http://localhost:8501

## Usage

### Running Evaluations

1. **Select Evaluation Type**:
   - **Local**: Runs the DSL generator service directly
   - **API-based**: Calls the running API server

2. **Choose Test Cases**:
   - Run all test cases, or select specific ones
   - Test cases are loaded from `eval_prompts.json`

3. **View Results**:
   - Summary metrics (pass rate, latency, accuracy)
   - Interactive charts and visualizations
   - Detailed per-test results

### Viewing Reports

- Browse historical evaluation reports
- Compare performance across different runs
- Download reports as JSON files
- Filter and analyze results

### Managing Test Cases

- View current test cases in a table format
- Add new test cases with expected results
- Edit existing test cases
- Validate test case structure

## Dashboard Pages

### 1. Run New Evaluation
- Execute evaluations with real-time progress
- Choose between local and API-based execution
- Select specific test cases to run

### 2. View Reports
- Browse all historical evaluation reports
- Interactive charts and metrics
- Download reports for external analysis

### 3. Manage Test Cases
- Add, edit, and remove test cases
- Validate test case structure
- Bulk operations on test cases

### 4. Settings
- Environment variable status
- API configuration
- System information

## Charts and Visualizations

- **Latency Chart**: Response time per test case
- **Accuracy Chart**: Accuracy scores across test cases
- **Pass/Fail Distribution**: Success rate visualization
- **Summary Metrics**: Key performance indicators

## File Structure

```
evals/
├── streamlit_app.py          # Main Streamlit application
├── run_streamlit.py          # Launcher script
├── run_evals.py              # Local evaluation runner
├── run_evals_api.py          # API-based evaluation runner
├── eval_prompts.json         # Test case definitions
├── *.json                    # Historical evaluation reports
└── README_STREAMLIT.md       # This file
```

## Troubleshooting

### Common Issues

1. **Streamlit not found**:
   ```bash
   pip install streamlit plotly pandas
   ```

2. **Missing environment variables**:
   - Check your `.env` file
   - Ensure API keys are properly set

3. **API connection failed**:
   - Make sure the API server is running
   - Check the API port configuration

4. **No test cases found**:
   - Verify `eval_prompts.json` exists
   - Check JSON file format

### Environment Setup

For local evaluations, ensure:
- All required environment variables are set
- The DSL generator service can be imported
- Database connections are configured

For API evaluations, ensure:
- The API server is running on the correct port
- API endpoints are accessible
- Authentication is properly configured

## Development

### Adding New Features

1. Edit `streamlit_app.py` to add new pages or functionality
2. Update the navigation in the sidebar
3. Add new visualization functions as needed
4. Test with different evaluation scenarios

### Customizing Visualizations

The dashboard uses Plotly for interactive charts. You can:
- Modify chart types and styling
- Add new chart types
- Customize color schemes
- Add interactive features

### Extending Test Case Management

- Add validation for new test case fields
- Implement bulk operations
- Add import/export functionality
- Create test case templates

## API Integration

The dashboard supports both local and API-based evaluation modes:

- **Local Mode**: Direct service integration
- **API Mode**: HTTP API calls to running server

Switch between modes using the radio buttons in the "Run New Evaluation" page.

## Performance

- Large evaluation reports may take time to load
- Consider pagination for very large datasets
- Charts are optimized for up to 1000 test cases
- Use filters to narrow down results for better performance
