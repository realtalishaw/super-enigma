#!/usr/bin/env python3
"""
Streamlit frontend for the workflow automation engine evals system.
Provides a web interface to run evaluations, view results, and manage test cases.
"""

import streamlit as st
import json
import asyncio
import time
import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import evaluation modules
from run_evals import run_evaluation as run_local_eval
from run_evals_api import run_evaluation as run_api_eval

# Page configuration
st.set_page_config(
    page_title="Workflow Automation Engine - Evals Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-metric {
        border-left-color: #28a745;
    }
    .warning-metric {
        border-left-color: #ffc107;
    }
    .error-metric {
        border-left-color: #dc3545;
    }
    .eval-result-card {
        border: 1px solid #ddd;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .eval-pass {
        border-left: 4px solid #28a745;
        background-color: #f8fff9;
    }
    .eval-fail {
        border-left: 4px solid #dc3545;
        background-color: #fff8f8;
    }
    .nav-button {
        margin: 0.25rem;
        font-weight: 500;
    }
    .nav-button-primary {
        background-color: #1f77b4 !important;
        color: white !important;
        border: 1px solid #1f77b4 !important;
    }
    .nav-button-secondary {
        background-color: #f0f2f6 !important;
        color: #262730 !important;
        border: 1px solid #d0d7de !important;
    }
</style>
""", unsafe_allow_html=True)

def load_eval_prompts() -> List[Dict[str, Any]]:
    """Load evaluation prompts from JSON file."""
    try:
        eval_file_path = Path(__file__).parent / "eval_prompts.json"
        with open(eval_file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"eval_prompts.json not found at {eval_file_path}")
        return []
    except json.JSONDecodeError:
        st.error("eval_prompts.json contains invalid JSON")
        return []

def load_eval_reports() -> List[Dict[str, Any]]:
    """Load all evaluation reports from the evals directory."""
    evals_dir = Path(__file__).parent
    reports = []
    
    for file_path in evals_dir.glob("*eval_report*.json"):
        try:
            with open(file_path, "r") as f:
                report = json.load(f)
                report["filename"] = file_path.name
                report["file_path"] = str(file_path)
                reports.append(report)
        except (json.JSONDecodeError, IOError) as e:
            st.warning(f"Could not load report {file_path.name}: {e}")
    
    # Sort by timestamp (newest first)
    reports.sort(key=lambda x: x.get("run_timestamp", ""), reverse=True)
    return reports

def display_summary_metrics(summary: Dict[str, Any]):
    """Display summary metrics in a nice card layout."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Test Cases",
            value=summary.get("total_cases", 0),
            help="Number of test cases in the evaluation"
        )
    
    with col2:
        pass_rate = summary.get("pass_rate_percent", 0)
        st.metric(
            label="Pass Rate",
            value=f"{pass_rate:.1f}%",
            delta=None,
            help="Percentage of test cases that passed"
        )
    
    with col3:
        avg_latency = summary.get("average_latency_ms", 0)
        st.metric(
            label="Avg Latency",
            value=f"{avg_latency:.0f}ms",
            help="Average response time in milliseconds"
        )
    
    with col4:
        avg_accuracy = summary.get("average_accuracy_on_pass", 0)
        st.metric(
            label="Avg Accuracy",
            value=f"{avg_accuracy:.2f}",
            help="Average accuracy score for passed tests"
        )

def create_latency_chart(results: List[Dict[str, Any]]):
    """Create a latency distribution chart."""
    df = pd.DataFrame(results)
    df['case_number'] = range(1, len(df) + 1)
    
    fig = px.bar(
        df, 
        x='case_number', 
        y='latency_ms',
        title="Latency by Test Case",
        labels={'case_number': 'Test Case', 'latency_ms': 'Latency (ms)'},
        color='latency_ms',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        showlegend=False,
        height=400,
        xaxis_title="Test Case Number",
        yaxis_title="Latency (milliseconds)"
    )
    
    return fig

def create_accuracy_chart(results: List[Dict[str, Any]]):
    """Create an accuracy distribution chart."""
    df = pd.DataFrame(results)
    df['case_number'] = range(1, len(df) + 1)
    
    fig = px.bar(
        df, 
        x='case_number', 
        y='accuracy_score',
        title="Accuracy Score by Test Case",
        labels={'case_number': 'Test Case', 'accuracy_score': 'Accuracy Score'},
        color='accuracy_score',
        color_continuous_scale='RdYlGn',
        range_color=[0, 1]
    )
    
    fig.update_layout(
        showlegend=False,
        height=400,
        xaxis_title="Test Case Number",
        yaxis_title="Accuracy Score"
    )
    
    return fig

def create_pass_fail_chart(results: List[Dict[str, Any]]):
    """Create a pass/fail pie chart."""
    pass_count = sum(1 for r in results if r.get("is_valid_schema", False))
    fail_count = len(results) - pass_count
    
    fig = go.Figure(data=[go.Pie(
        labels=['Pass', 'Fail'],
        values=[pass_count, fail_count],
        marker_colors=['#28a745', '#dc3545']
    )])
    
    fig.update_layout(
        title="Pass/Fail Distribution",
        height=400
    )
    
    return fig

def display_eval_results(results: List[Dict[str, Any]]):
    """Display detailed evaluation results."""
    st.subheader("Detailed Results")
    
    for i, result in enumerate(results):
        status_class = "eval-pass" if result.get("is_valid_schema", False) else "eval-fail"
        status_icon = "✅" if result.get("is_valid_schema", False) else "❌"
        
        with st.expander(f"{status_icon} {result.get('case_id', f'Case {i+1}')}", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Latency:** {result.get('latency_ms', 0)}ms")
                st.write(f"**Accuracy:** {result.get('accuracy_score', 0):.2f}")
            
            with col2:
                st.write(f"**Steps Generated:** {result.get('steps_generated', 0)}")
                st.write(f"**Valid Schema:** {'Yes' if result.get('is_valid_schema', False) else 'No'}")
            
            with col3:
                if result.get('error_message'):
                    st.error(f"**Error:** {result['error_message']}")
                else:
                    st.success("No errors")
            
            st.write(f"**Prompt:** {result.get('prompt', 'N/A')}")
            
            # Show generated DSL if available
            if result.get('generated_dsl'):
                with st.expander("Generated DSL", expanded=False):
                    st.json(result['generated_dsl'])

def run_evaluation_async(eval_type: str = "local"):
    """Run evaluation asynchronously and return results."""
    if eval_type == "local":
        return asyncio.run(run_local_eval())
    else:
        return asyncio.run(run_api_eval())

def create_time_series_charts(reports: List[Dict[str, Any]]):
    """Create time-series charts showing performance over time."""
    if not reports:
        return None, None, None
    
    # Prepare data for time series
    data = []
    for report in reports:
        timestamp = datetime.fromisoformat(report.get("run_timestamp", "").replace("Z", "+00:00"))
        summary = report.get("summary", {})
        
        data.append({
            "timestamp": timestamp,
            "date": timestamp.strftime("%Y-%m-%d %H:%M"),
            "pass_rate": summary.get("pass_rate_percent", 0),
            "avg_latency": summary.get("average_latency_ms", 0),
            "avg_accuracy": summary.get("average_accuracy_on_pass", 0),
            "total_cases": summary.get("total_cases", 0)
        })
    
    df = pd.DataFrame(data)
    df = df.sort_values("timestamp")
    
    # Pass rate over time
    fig_pass_rate = px.line(
        df, 
        x="timestamp", 
        y="pass_rate",
        title="Pass Rate Over Time",
        labels={"pass_rate": "Pass Rate (%)", "timestamp": "Date"},
        markers=True
    )
    fig_pass_rate.update_layout(height=300, xaxis_title="Date", yaxis_title="Pass Rate (%)")
    
    # Latency over time
    fig_latency = px.line(
        df, 
        x="timestamp", 
        y="avg_latency",
        title="Average Latency Over Time",
        labels={"avg_latency": "Latency (ms)", "timestamp": "Date"},
        markers=True,
        color_discrete_sequence=["orange"]
    )
    fig_latency.update_layout(height=300, xaxis_title="Date", yaxis_title="Latency (ms)")
    
    # Accuracy over time
    fig_accuracy = px.line(
        df, 
        x="timestamp", 
        y="avg_accuracy",
        title="Average Accuracy Over Time",
        labels={"avg_accuracy": "Accuracy Score", "timestamp": "Date"},
        markers=True,
        color_discrete_sequence=["green"]
    )
    fig_accuracy.update_layout(height=300, xaxis_title="Date", yaxis_title="Accuracy Score")
    
    return fig_pass_rate, fig_latency, fig_accuracy

def generate_ai_analysis(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate AI-powered analysis of evaluation data with deep pattern recognition."""
    if not reports:
        return {"error": "No data to analyze"}
    
    # Flatten all results
    all_results = []
    for report in reports:
        for result in report.get("results", []):
            result["report_timestamp"] = report.get("run_timestamp")
            all_results.append(result)
    
    if not all_results:
        return {"error": "No evaluation results found"}
    
    # Calculate key metrics
    total_cases = len(all_results)
    successful_cases = [r for r in all_results if r.get("is_valid_schema", False)]
    failed_cases = [r for r in all_results if not r.get("is_valid_schema", False)]
    
    success_rate = len(successful_cases) / total_cases * 100 if total_cases > 0 else 0
    avg_accuracy = np.mean([r.get("accuracy_score", 0) for r in successful_cases]) if successful_cases else 0
    avg_latency = np.mean([r.get("latency_ms", 0) for r in all_results]) if all_results else 0
    
    # Deep pattern analysis
    pattern_insights = analyze_prompt_patterns(all_results)
    workflow_insights = analyze_workflow_complexity(all_results)
    performance_insights = analyze_performance_patterns(all_results)
    failure_insights = analyze_failure_patterns_deep(failed_cases)
    
    # Generate intelligent insights
    insights = []
    
    # Performance insights
    if success_rate > 80:
        insights.append(f"🎉 Excellent performance! {success_rate:.1f}% success rate")
    elif success_rate > 60:
        insights.append(f"✅ Good performance with {success_rate:.1f}% success rate")
    else:
        insights.append(f"⚠️ Performance needs improvement: {success_rate:.1f}% success rate")
    
    # Add pattern-based insights
    insights.extend(pattern_insights)
    insights.extend(workflow_insights)
    insights.extend(performance_insights)
    insights.extend(failure_insights)
    
    # Generate intelligent recommendations
    recommendations = generate_intelligent_recommendations(
        all_results, successful_cases, failed_cases, 
        pattern_insights, workflow_insights, performance_insights
    )
    
    return {
        "summary": {
            "total_evaluations": len(reports),
            "total_cases": total_cases,
            "success_rate": success_rate,
            "avg_accuracy": avg_accuracy,
            "avg_latency_seconds": avg_latency / 1000
        },
        "insights": insights,
        "recommendations": recommendations,
        "pattern_analysis": {
            "prompt_patterns": pattern_insights,
            "workflow_complexity": workflow_insights,
            "performance_patterns": performance_insights,
            "failure_patterns": failure_insights
        }
    }

def analyze_prompt_patterns(all_results: List[Dict[str, Any]]) -> List[str]:
    """Analyze prompt characteristics and their impact on performance."""
    insights = []
    
    # Analyze prompt length vs success
    short_prompts = [r for r in all_results if len(r.get("prompt", "")) < 50]
    medium_prompts = [r for r in all_results if 50 <= len(r.get("prompt", "")) < 150]
    long_prompts = [r for r in all_results if len(r.get("prompt", "")) >= 150]
    
    def success_rate(results):
        return len([r for r in results if r.get("is_valid_schema", False)]) / len(results) * 100 if results else 0
    
    short_success = success_rate(short_prompts)
    medium_success = success_rate(medium_prompts)
    long_success = success_rate(long_prompts)
    
    if short_prompts and medium_prompts and long_prompts:
        if short_success < medium_success - 10:
            insights.append(f"📝 Vague prompts perform poorly: {short_success:.1f}% vs {medium_success:.1f}% for detailed prompts")
        elif long_success > medium_success + 10:
            insights.append(f"📝 Detailed prompts perform better: {long_success:.1f}% vs {medium_success:.1f}% for medium-length prompts")
    
    # Analyze prompt specificity
    vague_keywords = ["help", "automate", "manage", "handle", "do something"]
    specific_keywords = ["when", "if", "send", "create", "update", "delete", "post"]
    
    vague_prompts = [r for r in all_results if any(keyword in r.get("prompt", "").lower() for keyword in vague_keywords)]
    specific_prompts = [r for r in all_results if any(keyword in r.get("prompt", "").lower() for keyword in specific_keywords)]
    
    vague_success = success_rate(vague_prompts)
    specific_success = success_rate(specific_prompts)
    
    if vague_prompts and specific_prompts and abs(vague_success - specific_success) > 15:
        if vague_success < specific_success:
            insights.append(f"🎯 Specific prompts work much better: {specific_success:.1f}% vs {vague_success:.1f}% for vague requests")
        else:
            insights.append(f"🤔 Interesting: Vague prompts actually perform better ({vague_success:.1f}% vs {specific_success:.1f}%)")
    
    return insights

def analyze_workflow_complexity(all_results: List[Dict[str, Any]]) -> List[str]:
    """Analyze workflow complexity patterns."""
    insights = []
    
    # Analyze multi-step vs single-step workflows
    multi_step = [r for r in all_results if r.get("steps_generated", 0) > 1]
    single_step = [r for r in all_results if r.get("steps_generated", 0) == 1]
    
    def success_rate(results):
        return len([r for r in results if r.get("is_valid_schema", False)]) / len(results) * 100 if results else 0
    
    multi_success = success_rate(multi_step)
    single_success = success_rate(single_step)
    
    if multi_step and single_step:
        if multi_success > single_success + 10:
            insights.append(f"🔗 Complex workflows perform better: {multi_success:.1f}% vs {single_success:.1f}% for simple workflows")
        elif single_success > multi_success + 10:
            insights.append(f"⚡ Simple workflows are more reliable: {single_success:.1f}% vs {multi_success:.1f}% for complex workflows")
    
    # Analyze accuracy vs complexity
    if multi_step and single_step:
        multi_accuracy = np.mean([r.get("accuracy_score", 0) for r in multi_step if r.get("is_valid_schema", False)])
        single_accuracy = np.mean([r.get("accuracy_score", 0) for r in single_step if r.get("is_valid_schema", False)])
        
        if multi_accuracy > single_accuracy + 0.1:
            insights.append(f"🎯 Complex workflows achieve higher accuracy: {multi_accuracy:.2f} vs {single_accuracy:.2f}")
        elif single_accuracy > multi_accuracy + 0.1:
            insights.append(f"🎯 Simple workflows are more accurate: {single_accuracy:.2f} vs {multi_accuracy:.2f}")
    
    return insights

def analyze_performance_patterns(all_results: List[Dict[str, Any]]) -> List[str]:
    """Analyze performance patterns and bottlenecks."""
    insights = []
    
    # Analyze latency patterns
    fast_cases = [r for r in all_results if r.get("latency_ms", 0) < 3000]
    slow_cases = [r for r in all_results if r.get("latency_ms", 0) > 8000]
    
    def success_rate(results):
        return len([r for r in results if r.get("is_valid_schema", False)]) / len(results) * 100 if results else 0
    
    fast_success = success_rate(fast_cases)
    slow_success = success_rate(slow_cases)
    
    if fast_cases and slow_cases:
        if fast_success > slow_success + 15:
            insights.append(f"⚡ Fast responses are more successful: {fast_success:.1f}% vs {slow_success:.1f}% for slow responses")
        elif slow_success > fast_success + 15:
            insights.append(f"🤔 Slow responses are more successful: {slow_success:.1f}% vs {fast_success:.1f}% - consider why")
    
    # Analyze accuracy vs latency correlation
    successful_cases = [r for r in all_results if r.get("is_valid_schema", False)]
    if successful_cases:
        latencies = [r.get("latency_ms", 0) for r in successful_cases]
        accuracies = [r.get("accuracy_score", 0) for r in successful_cases]
        
        if len(latencies) > 10:  # Need enough data for correlation
            correlation = np.corrcoef(latencies, accuracies)[0, 1]
            if correlation > 0.3:
                insights.append(f"📊 Higher latency correlates with better accuracy (r={correlation:.2f}) - system may be thinking more carefully")
            elif correlation < -0.3:
                insights.append(f"📊 Higher latency correlates with worse accuracy (r={correlation:.2f}) - may indicate system confusion")
    
    return insights

def analyze_failure_patterns_deep(failed_cases: List[Dict[str, Any]]) -> List[str]:
    """Deep analysis of failure patterns."""
    insights = []
    
    if not failed_cases:
        return insights
    
    # Analyze failure by prompt characteristics
    failed_prompts = [r.get("prompt", "") for r in failed_cases]
    
    # Check for common failure patterns
    vague_failures = [p for p in failed_prompts if len(p.split()) < 5]
    if vague_failures and len(vague_failures) > len(failed_cases) * 0.3:
        insights.append(f"🚨 {len(vague_failures)}/{len(failed_cases)} failures are from very short prompts - users need more guidance")
    
    # Check for specific failure keywords
    failure_keywords = ["automate", "help", "manage", "workflow", "process"]
    keyword_failures = [p for p in failed_prompts if any(kw in p.lower() for kw in failure_keywords)]
    if keyword_failures and len(keyword_failures) > len(failed_cases) * 0.4:
        insights.append(f"🔍 {len(keyword_failures)}/{len(failed_cases)} failures contain generic automation keywords - prompts need more specificity")
    
    # Analyze error message patterns
    error_messages = [r.get("error_message", "") for r in failed_cases if r.get("error_message")]
    if error_messages:
        # Look for common error themes
        trigger_errors = [e for e in error_messages if "trigger" in e.lower()]
        action_errors = [e for e in error_messages if "action" in e.lower()]
        schema_errors = [e for e in error_messages if "schema" in e.lower()]
        
        if trigger_errors and len(trigger_errors) > len(error_messages) * 0.4:
            insights.append(f"🎯 {len(trigger_errors)}/{len(error_messages)} errors are trigger-related - improve trigger selection logic")
        
        if action_errors and len(action_errors) > len(error_messages) * 0.4:
            insights.append(f"⚙️ {len(action_errors)}/{len(error_messages)} errors are action-related - improve action mapping")
        
        if schema_errors and len(schema_errors) > len(error_messages) * 0.3:
            insights.append(f"📋 {len(schema_errors)}/{len(error_messages)} errors are schema-related - improve validation")
    
    return insights

def generate_intelligent_recommendations(all_results, successful_cases, failed_cases, 
                                       pattern_insights, workflow_insights, performance_insights) -> List[str]:
    """Generate intelligent, data-driven recommendations."""
    recommendations = []
    
    # Analyze patterns to generate specific recommendations
    success_rate = len(successful_cases) / len(all_results) * 100 if all_results else 0
    
    # Prompt engineering recommendations
    if any("vague prompts" in insight.lower() for insight in pattern_insights):
        recommendations.append("🎯 Add prompt templates and examples to guide users toward more specific requests")
        recommendations.append("📝 Implement prompt suggestions based on successful patterns")
    
    if any("detailed prompts" in insight.lower() for insight in pattern_insights):
        recommendations.append("📚 Create a prompt library with high-performing examples")
        recommendations.append("💡 Add auto-completion for detailed prompt construction")
    
    # Workflow complexity recommendations
    if any("complex workflows" in insight.lower() for insight in workflow_insights):
        recommendations.append("🔗 Focus on improving multi-step workflow generation")
        recommendations.append("📊 Add workflow complexity scoring to help users understand requirements")
    
    if any("simple workflows" in insight.lower() for insight in workflow_insights):
        recommendations.append("⚡ Optimize for single-step workflows and add complexity gradually")
        recommendations.append("🎯 Create a 'simple mode' for basic automation needs")
    
    # Performance recommendations
    if any("fast responses" in insight.lower() for insight in performance_insights):
        recommendations.append("⚡ Implement aggressive caching for common patterns")
        recommendations.append("🚀 Optimize API calls and reduce context size for faster responses")
    
    if any("latency correlates" in insight.lower() for insight in performance_insights):
        recommendations.append("⏱️ Implement adaptive timeout based on prompt complexity")
        recommendations.append("🧠 Add confidence scoring to balance speed vs accuracy")
    
    # Failure-specific recommendations
    if any("trigger-related" in insight.lower() for insight in pattern_insights):
        recommendations.append("🎯 Improve trigger selection with better semantic matching")
        recommendations.append("📋 Add trigger validation and fallback options")
    
    if any("action-related" in insight.lower() for insight in pattern_insights):
        recommendations.append("⚙️ Enhance action mapping with better context understanding")
        recommendations.append("🔍 Add action suggestion system based on prompt analysis")
    
    # General recommendations based on success rate
    if success_rate < 70:
        recommendations.append("📈 Focus on improving core generation accuracy before adding features")
        recommendations.append("🔄 Implement A/B testing for different prompt strategies")
    
    if success_rate > 80:
        recommendations.append("🚀 System is performing well - focus on optimization and new features")
        recommendations.append("📊 Consider expanding test coverage to edge cases")
    
    return recommendations

def display_ai_insights(insights: Dict[str, Any]):
    """Display AI-generated insights in a nice format."""
    if "error" in insights:
        st.error(f"❌ {insights['error']}")
        return
    
    # Summary metrics
    st.subheader("📊 Analysis Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Success Rate", f"{insights['summary']['success_rate']:.1f}%")
    with col2:
        st.metric("Avg Accuracy", f"{insights['summary']['avg_accuracy']:.2f}")
    with col3:
        st.metric("Avg Latency", f"{insights['summary']['avg_latency_seconds']:.1f}s")
    with col4:
        st.metric("Total Cases", f"{insights['summary']['total_cases']}")
    
    # Key insights
    st.subheader("💡 Key Insights")
    for insight in insights["insights"]:
        st.info(insight)
    
    # Recommendations
    st.subheader("🎯 Improvement Recommendations")
    for i, rec in enumerate(insights["recommendations"], 1):
        st.write(f"{i}. {rec}")
    
    # Pattern analysis breakdown
    if "pattern_analysis" in insights:
        st.subheader("🔍 Deep Pattern Analysis")
        
        # Prompt patterns
        if insights["pattern_analysis"]["prompt_patterns"]:
            st.write("**📝 Prompt Patterns:**")
            for pattern in insights["pattern_analysis"]["prompt_patterns"]:
                st.write(f"  • {pattern}")
        
        # Workflow complexity
        if insights["pattern_analysis"]["workflow_complexity"]:
            st.write("**🔗 Workflow Complexity:**")
            for complexity in insights["pattern_analysis"]["workflow_complexity"]:
                st.write(f"  • {complexity}")
        
        # Performance patterns
        if insights["pattern_analysis"]["performance_patterns"]:
            st.write("**⚡ Performance Patterns:**")
            for perf in insights["pattern_analysis"]["performance_patterns"]:
                st.write(f"  • {perf}")
        
        # Failure patterns
        if insights["pattern_analysis"]["failure_patterns"]:
            st.write("**🚨 Failure Patterns:**")
            for failure in insights["pattern_analysis"]["failure_patterns"]:
                st.write(f"  • {failure}")

def calculate_overall_averages(reports: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate overall averages across all reports."""
    if not reports:
        return {"pass_rate": 0, "latency": 0, "accuracy": 0, "total_cases": 0}
    
    total_pass_rate = 0
    total_latency = 0
    total_accuracy = 0
    total_cases = 0
    valid_reports = 0
    
    for report in reports:
        summary = report.get("summary", {})
        if summary:
            total_pass_rate += summary.get("pass_rate_percent", 0)
            total_latency += summary.get("average_latency_ms", 0)
            total_accuracy += summary.get("average_accuracy_on_pass", 0)
            total_cases += summary.get("total_cases", 0)
            valid_reports += 1
    
    if valid_reports == 0:
        return {"pass_rate": 0, "latency": 0, "accuracy": 0, "total_cases": 0}
    
    return {
        "pass_rate": total_pass_rate / valid_reports,
        "latency": total_latency / valid_reports,
        "accuracy": total_accuracy / valid_reports,
        "total_cases": total_cases
    }

def display_dashboard_homepage():
    """Display the main dashboard homepage with time-series charts."""
    st.header("📊 Evaluation Performance Dashboard")
    
    # Load all reports
    reports = load_eval_reports()
    
    if not reports:
        st.warning("No evaluation reports found. Run some evaluations to see the dashboard!")
        return
    
    # Overall averages across all reports
    overall_avg = calculate_overall_averages(reports)
    st.subheader("Overall Performance Summary")
    
    # Display overall averages
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Overall Pass Rate",
            value=f"{overall_avg['pass_rate']:.1f}%",
            help="Average pass rate across all evaluation runs"
        )
    
    with col2:
        st.metric(
            label="Overall Avg Latency",
            value=f"{overall_avg['latency']/1000:.1f}s",
            help="Average latency across all evaluation runs"
        )
    
    with col3:
        st.metric(
            label="Overall Avg Accuracy",
            value=f"{overall_avg['accuracy']:.2f}",
            help="Average accuracy across all evaluation runs"
        )
    
    with col4:
        st.metric(
            label="Total Test Cases",
            value=f"{overall_avg['total_cases']:.0f}",
            help="Total test cases run across all evaluations"
        )
    
    # Time series charts
    st.subheader("Performance Over Time")
    
    fig_pass_rate, fig_latency, fig_accuracy = create_time_series_charts(reports)
    
    if fig_pass_rate:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_pass_rate, use_container_width=True)
        with col2:
            st.plotly_chart(fig_latency, use_container_width=True)
        
        st.plotly_chart(fig_accuracy, use_container_width=True)
    
    # Recent reports table
    st.subheader("Recent Evaluation Runs")
    
    if reports:
        # Create a summary table
        report_data = []
        for report in reports[:10]:  # Show last 10 reports
            timestamp = report.get("run_timestamp", "")
            summary = report.get("summary", {})
            
            report_data.append({
                "Date": timestamp[:19] if timestamp else "Unknown",
                "Pass Rate": f"{summary.get('pass_rate_percent', 0):.1f}%",
                "Avg Latency": f"{summary.get('average_latency_ms', 0):.0f}ms",
                "Avg Accuracy": f"{summary.get('average_accuracy_on_pass', 0):.2f}",
                "Test Cases": summary.get("total_cases", 0)
            })
        
        df_reports = pd.DataFrame(report_data)
        st.dataframe(df_reports, use_container_width=True)
    
    # AI Analysis Section
    st.subheader("🤖 AI Analysis & Insights")
    
    if st.button("🔍 Generate AI Analysis", type="primary"):
        with st.spinner("AI is analyzing your evaluation data..."):
            ai_insights = generate_ai_analysis(reports)
            display_ai_insights(ai_insights)
    

def run_evaluation_with_progress(eval_type: str = "local", selected_cases: List[Dict] = None):
    """Run evaluation with real-time progress updates."""
    import asyncio
    import time
    from datetime import datetime
    
    # Create progress containers
    progress_container = st.container()
    results_container = st.container()
    
    with progress_container:
        st.subheader("🚀 Running Evaluation...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        current_case_text = st.empty()
        
        # Create columns for real-time results
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Cases Completed", "0")
        with col2:
            st.metric("Pass Rate", "0%")
        with col3:
            st.metric("Avg Latency", "0ms")
        with col4:
            st.metric("Avg Accuracy", "0.00")
    
    # Initialize tracking variables
    completed_cases = 0
    total_cases = len(selected_cases) if selected_cases else 0
    results = []
    pass_count = 0
    total_latency = 0
    total_accuracy = 0
    
    try:
        # Load test cases
        test_cases = load_eval_prompts()
        if selected_cases:
            test_cases = [case for case in test_cases if case["id"] in [c["id"] for c in selected_cases]]
        
        total_cases = len(test_cases)
        
        # Initialize generator or API client
        if eval_type == "local":
            from services.dsl_generator.generator import DSLGeneratorService, GenerationRequest
            generator = DSLGeneratorService()
            asyncio.run(generator.initialize())
            
            # Initialize cache service
            try:
                from api.cache_service import global_cache_service
                asyncio.run(global_cache_service.initialize())
                generator.set_global_cache(global_cache_service.get_catalog_cache())
            except Exception as e:
                st.warning(f"Cache service initialization failed: {e}")
        
        # Run each test case
        for i, test_case in enumerate(test_cases):
            current_case_text.text(f"Running: {test_case['id']}")
            
            # Update progress
            progress = (i + 1) / total_cases
            progress_bar.progress(progress)
            status_text.text(f"Processing case {i+1}/{total_cases}")
            
            # Run the test case
            start_time = time.time()
            
            if eval_type == "local":
                request = GenerationRequest(
                    user_prompt=test_case["prompt"],
                    selected_apps=test_case["selected_apps"]
                )
                response = asyncio.run(generator.generate_workflow(request))
                latency_ms = (time.time() - start_time) * 1000
                
                # Score the result
                score = {
                    "case_id": test_case["id"],
                    "prompt": test_case["prompt"],
                    "latency_ms": round(latency_ms),
                    "is_valid_schema": False,
                    "accuracy_score": 0.0,
                    "steps_generated": 0,
                    "error_message": response.error_message,
                    "generated_dsl": response.dsl_template
                }
                
                if response.success and response.dsl_template:
                    score["is_valid_schema"] = True
                    # Calculate accuracy (simplified)
                    try:
                        workflow = response.dsl_template.get('workflow', {})
                        generated_actions = {action.get('action_name', '') for action in workflow.get('actions', [])}
                        score["steps_generated"] = len(generated_actions)
                        
                        # Simple accuracy calculation
                        correct_checks = 0
                        total_checks = 0
                        
                        # Check trigger
                        total_checks += 1
                        if workflow.get('triggers') and workflow['triggers'][0].get('composio_trigger_slug') == test_case['expected']['trigger_slug']:
                            correct_checks += 1
                        
                        # Check actions
                        total_checks += 1
                        if all(action in generated_actions for action in test_case['expected']['action_slugs']):
                            correct_checks += 1
                        
                        # Check min steps
                        total_checks += 1
                        if score["steps_generated"] >= test_case['expected']['min_steps']:
                            correct_checks += 1
                        
                        score["accuracy_score"] = round(correct_checks / total_checks, 2) if total_checks > 0 else 0
                    except Exception as e:
                        score["error_message"] = f"Scoring error: {str(e)}"
            else:
                # API-based evaluation
                import httpx
                API_BASE_URL = "http://localhost:8001"
                SUGGESTIONS_ENDPOINT = f"{API_BASE_URL}/api/suggestions:generate"
                
                payload = {
                    "user_id": "eval_user",
                    "user_request": test_case["prompt"],
                    "selected_apps": test_case["selected_apps"],
                    "num_suggestions": 1
                }
                
                try:
                    async def call_api():
                        async with httpx.AsyncClient() as client:
                            response = await client.post(SUGGESTIONS_ENDPOINT, json=payload, timeout=60.0)
                            response.raise_for_status()
                            return response.json()
                    
                    api_response = asyncio.run(call_api())
                    latency_ms = (time.time() - start_time) * 1000
                    
                    score = {
                        "case_id": test_case["id"],
                        "prompt": test_case["prompt"],
                        "latency_ms": round(latency_ms),
                        "is_valid_schema": "error" not in api_response,
                        "accuracy_score": 0.0,
                        "steps_generated": 0,
                        "error_message": api_response.get("error"),
                        "generated_dsl": api_response
                    }
                    
                    if "error" not in api_response:
                        # Calculate accuracy for API response
                        try:
                            if "suggestions" in api_response and api_response["suggestions"]:
                                suggestion = api_response["suggestions"][0]
                                dsl_parametric = suggestion.get("dsl_parametric", {})
                                actions = dsl_parametric.get("actions", [])
                                generated_actions = {action.get('action_name', '') for action in actions}
                                score["steps_generated"] = len(generated_actions)
                                
                                # Simple accuracy calculation
                                correct_checks = 0
                                total_checks = 0
                                
                                # Check trigger
                                total_checks += 1
                                trigger = dsl_parametric.get("trigger", {})
                                if trigger and trigger.get("composio_trigger_slug") == test_case['expected']['trigger_slug']:
                                    correct_checks += 1
                                
                                # Check actions
                                total_checks += 1
                                if all(action in generated_actions for action in test_case['expected']['action_slugs']):
                                    correct_checks += 1
                                
                                # Check min steps
                                total_checks += 1
                                if score["steps_generated"] >= test_case['expected']['min_steps']:
                                    correct_checks += 1
                                
                                score["accuracy_score"] = round(correct_checks / total_checks, 2) if total_checks > 0 else 0
                        except Exception as e:
                            score["error_message"] = f"Scoring error: {str(e)}"
                
                except Exception as e:
                    latency_ms = (time.time() - start_time) * 1000
                    score = {
                        "case_id": test_case["id"],
                        "prompt": test_case["prompt"],
                        "latency_ms": round(latency_ms),
                        "is_valid_schema": False,
                        "accuracy_score": 0.0,
                        "steps_generated": 0,
                        "error_message": str(e),
                        "generated_dsl": None
                    }
            
            results.append(score)
            completed_cases += 1
            
            # Update real-time metrics
            if score["is_valid_schema"]:
                pass_count += 1
                total_accuracy += score["accuracy_score"]
            
            total_latency += score["latency_ms"]
            
            # Update metrics
            with col1:
                st.metric("Cases Completed", f"{completed_cases}/{total_cases}")
            with col2:
                pass_rate = (pass_count / completed_cases) * 100 if completed_cases > 0 else 0
                st.metric("Pass Rate", f"{pass_rate:.1f}%")
            with col3:
                avg_latency = total_latency / completed_cases if completed_cases > 0 else 0
                st.metric("Avg Latency", f"{avg_latency:.0f}ms")
            with col4:
                avg_accuracy = total_accuracy / pass_count if pass_count > 0 else 0
                st.metric("Avg Accuracy", f"{avg_accuracy:.2f}")
            
            # Show current result
            status_icon = "✅" if score["is_valid_schema"] else "❌"
            st.write(f"{status_icon} **{test_case['id']}**: {score['latency_ms']}ms, Accuracy: {score['accuracy_score']:.2f}")
        
        # Final results
        progress_bar.progress(1.0)
        status_text.text("✅ Evaluation complete!")
        current_case_text.text("")
        
        # Save report
        report = {
            "run_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_cases": total_cases,
                "pass_rate_percent": (pass_count / total_cases) * 100 if total_cases > 0 else 0,
                "average_latency_ms": total_latency / total_cases if total_cases > 0 else 0,
                "average_accuracy_on_pass": total_accuracy / pass_count if pass_count > 0 else 0,
            },
            "results": results
        }
        
        # Save report file
        evals_dir = Path(__file__).parent
        report_filename = f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = evals_dir / report_filename
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        st.success(f"✅ Evaluation completed! Report saved to {report_filename}")
        
        # Show final results
        with results_container:
            st.subheader("📊 Final Results")
            display_summary_metrics(report["summary"])
            
            # Show charts
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(create_latency_chart(results), use_container_width=True)
            with col2:
                st.plotly_chart(create_pass_fail_chart(results), use_container_width=True)
            
            st.plotly_chart(create_accuracy_chart(results), use_container_width=True)
            
            # Show detailed results
            display_eval_results(results)
        
        return report
        
    except Exception as e:
        st.error(f"❌ Evaluation failed: {str(e)}")
        progress_bar.progress(0)
        status_text.text("Evaluation failed")
        return None

def main():
    """Main Streamlit application."""
    
    # Initialize session state
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    
    # Header
    st.markdown('<h1 class="main-header">🚀 Workflow Automation Engine - Evals Dashboard</h1>', unsafe_allow_html=True)
    
    # Navigation buttons
    st.subheader("Navigation")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        if st.button("🏠 Dashboard", use_container_width=True, type="primary" if st.session_state.page == "Dashboard" else "secondary"):
            st.session_state.page = "Dashboard"
            st.rerun()
    
    with col2:
        if st.button("🚀 Run Evaluation", use_container_width=True, type="primary" if st.session_state.page == "Run New Evaluation" else "secondary"):
            st.session_state.page = "Run New Evaluation"
            st.rerun()
    
    with col3:
        if st.button("📊 View Reports", use_container_width=True, type="primary" if st.session_state.page == "View Reports" else "secondary"):
            st.session_state.page = "View Reports"
            st.rerun()
    
    with col4:
        if st.button("📈 API Usage", use_container_width=True, type="primary" if st.session_state.page == "API Usage" else "secondary"):
            st.session_state.page = "API Usage"
            st.rerun()
    
    with col5:
        if st.button("🔧 Test Cases", use_container_width=True, type="primary" if st.session_state.page == "Manage Test Cases" else "secondary"):
            st.session_state.page = "Manage Test Cases"
            st.rerun()
    
    with col6:
        if st.button("⚙️ Settings", use_container_width=True, type="primary" if st.session_state.page == "Settings" else "secondary"):
            st.session_state.page = "Settings"
            st.rerun()
    
    # Add some spacing
    st.markdown("---")
    
    # Display the selected page
    if st.session_state.page == "Dashboard":
        display_dashboard_homepage()
    elif st.session_state.page == "Run New Evaluation":
        run_evaluation_page()
    elif st.session_state.page == "View Reports":
        view_reports_page()
    elif st.session_state.page == "API Usage":
        api_usage_page()
    elif st.session_state.page == "Manage Test Cases":
        manage_test_cases_page()
    elif st.session_state.page == "Settings":
        settings_page()

def run_evaluation_page():
    """Page for running new evaluations."""
    st.header("Run New Evaluation")
    
    # Evaluation type selection
    eval_type = st.radio(
        "Select evaluation type:",
        ["Local (Direct Service)", "API-based"],
        help="Local runs the service directly, API-based calls the running API server"
    )
    
    # Load test cases
    test_cases = load_eval_prompts()
    if not test_cases:
        st.error("No test cases found. Please check eval_prompts.json")
        return
    
    st.write(f"Found {len(test_cases)} test cases")
    
    # Test case selection
    selected_cases = None
    if st.checkbox("Select specific test cases", help="Uncheck to run all test cases"):
        selected_case_ids = st.multiselect(
            "Choose test cases to run:",
            options=[case["id"] for case in test_cases],
            default=[case["id"] for case in test_cases]
        )
        selected_cases = [case for case in test_cases if case["id"] in selected_case_ids]
    else:
        selected_cases = test_cases
    
    # Run evaluation button
    if st.button("🚀 Run Evaluation", type="primary"):
        if not selected_cases:
            st.error("No test cases selected")
            return
        
        # Check environment variables for local evaluation
        if eval_type == "local":
            required_vars = ["ANTHROPIC_API_KEY", "GROQ_API_KEY"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                st.error(f"Missing required environment variables: {', '.join(missing_vars)}")
                return
        
        # Run evaluation with real-time progress
        eval_type_key = "local" if eval_type == "Local (Direct Service)" else "api"
        run_evaluation_with_progress(eval_type_key, selected_cases)

def display_evaluation_results(report: Dict[str, Any]):
    """Display evaluation results from a report."""
    st.header("Evaluation Results")
    
    # Summary metrics
    if "summary" in report:
        display_summary_metrics(report["summary"])
    
    # Charts
    if "results" in report:
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_latency_chart(report["results"]), use_container_width=True)
        
        with col2:
            st.plotly_chart(create_pass_fail_chart(report["results"]), use_container_width=True)
        
        # Accuracy chart
        st.plotly_chart(create_accuracy_chart(report["results"]), use_container_width=True)
        
        # Detailed results
        display_eval_results(report["results"])

def view_reports_page():
    """Page for viewing historical evaluation reports."""
    st.header("View Evaluation Reports")
    
    reports = load_eval_reports()
    
    if not reports:
        st.warning("No evaluation reports found")
        return
    
    st.write(f"Found {len(reports)} evaluation reports")
    
    # Report selection
    report_options = [f"{report['filename']} - {report.get('run_timestamp', 'Unknown time')}" for report in reports]
    selected_report_idx = st.selectbox("Select a report to view:", range(len(reports)), format_func=lambda x: report_options[x])
    
    if selected_report_idx is not None:
        selected_report = reports[selected_report_idx]
        display_evaluation_results(selected_report)
        
        # Download button
        report_json = json.dumps(selected_report, indent=2)
        st.download_button(
            label="📥 Download Report as JSON",
            data=report_json,
            file_name=selected_report['filename'],
            mime="application/json"
        )

def manage_test_cases_page():
    """Page for managing test cases."""
    st.header("Manage Test Cases")
    
    test_cases = load_eval_prompts()
    
    if not test_cases:
        st.error("No test cases found")
        return
    
    st.write(f"Current test cases: {len(test_cases)}")
    
    # Display test cases in a table
    df = pd.DataFrame(test_cases)
    st.dataframe(df[['id', 'prompt', 'selected_apps']], use_container_width=True)
    
    # Add new test case
    st.subheader("Add New Test Case")
    
    with st.form("add_test_case"):
        case_id = st.text_input("Case ID")
        prompt = st.text_area("Prompt")
        selected_apps = st.text_input("Selected Apps (comma-separated)")
        trigger_slug = st.text_input("Expected Trigger Slug")
        action_slugs = st.text_input("Expected Action Slugs (comma-separated)")
        min_steps = st.number_input("Minimum Steps", min_value=0, value=1)
        
        submitted = st.form_submit_button("Add Test Case")
        
        if submitted:
            if case_id and prompt:
                new_case = {
                    "id": case_id,
                    "prompt": prompt,
                    "selected_apps": [app.strip() for app in selected_apps.split(",") if app.strip()],
                    "expected": {
                        "apps": [app.strip() for app in selected_apps.split(",") if app.strip()],
                        "trigger_slug": trigger_slug,
                        "action_slugs": [action.strip() for action in action_slugs.split(",") if action.strip()],
                        "min_steps": min_steps
                    }
                }
                
                test_cases.append(new_case)
                
                # Save updated test cases
                eval_file_path = Path(__file__).parent / "eval_prompts.json"
                with open(eval_file_path, "w") as f:
                    json.dump(test_cases, f, indent=2)
                
                st.success("✅ Test case added successfully!")
                st.rerun()
            else:
                st.error("Please fill in Case ID and Prompt")

def api_usage_page():
    """Page for displaying API usage statistics and testing API endpoints."""
    st.header("📈 API Usage & Testing")
    
    # API Configuration
    st.subheader("API Configuration")
    col1, col2 = st.columns(2)
    
    with col1:
        api_base_url = st.text_input("API Base URL", value="http://localhost:8001", key="api_url")
    
    with col2:
        if st.button("🔄 Refresh Data", type="primary"):
            st.rerun()
    
    # Check API connectivity
    st.subheader("API Status")
    api_status = check_api_status(api_base_url)
    
    if api_status["connected"]:
        st.success(f"✅ API is running and accessible at {api_base_url}")
        
        # Tabs for different sections
        tab1, tab2, tab3 = st.tabs(["📊 Usage Statistics", "🔧 Test API Endpoints", "📋 API Documentation"])
        
        with tab1:
            # Get API usage data
            with st.spinner("Loading API usage data..."):
                usage_data = get_api_usage_data(api_base_url)
                
                if usage_data:
                    display_api_usage_stats(usage_data)
                else:
                    st.warning("No API usage data available. Make sure the API server is running with logging enabled.")
        
        with tab2:
            test_api_endpoints(api_base_url)
        
        with tab3:
            display_api_documentation(api_base_url)
    else:
        st.error(f"❌ Cannot connect to API at {api_base_url}")
        st.info("Make sure the API server is running and accessible")

def check_api_status(api_base_url: str) -> Dict[str, Any]:
    """Check if API is accessible."""
    import httpx
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{api_base_url}/health")
            return {
                "connected": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds() * 1000
            }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }

def get_api_usage_data(api_base_url: str) -> Dict[str, Any]:
    """Get API usage data from the server."""
    import httpx
    
    try:
        with httpx.Client(timeout=10.0) as client:
            # Try to get usage statistics from API
            response = client.get(f"{api_base_url}/api/usage/stats")
            if response.status_code == 200:
                data = response.json()
                # Wrap the data in the expected structure
                return {"usage_stats": data}
            
            # If no usage endpoint, try to get basic info
            response = client.get(f"{api_base_url}/api/status")
            if response.status_code == 200:
                return {"basic_info": response.json()}
            
            return None
    except Exception as e:
        st.error(f"Error fetching API data: {e}")
        return None

def display_api_usage_stats(usage_data: Dict[str, Any]):
    """Display API usage statistics."""
    
    # Basic API info
    if "basic_info" in usage_data:
        st.subheader("API Information")
        info = usage_data["basic_info"]
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Status", info.get("status", "Unknown"))
        with col2:
            st.metric("Version", info.get("version", "Unknown"))
        with col3:
            st.metric("Uptime", info.get("uptime", "Unknown"))
    
    # Usage statistics
    if "usage_stats" in usage_data:
        stats = usage_data["usage_stats"]
        
        st.subheader("Usage Statistics")
        
        # Overall metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Requests", stats.get("total_requests", 0))
        with col2:
            st.metric("Catalog Requests", stats.get("catalog_requests", 0))
        with col3:
            st.metric("Suggestions Requests", stats.get("suggestions_requests", 0))
        with col4:
            st.metric("Error Rate", f"{stats.get('error_rate', 0):.1f}%")
        
        # Request breakdown
        if "endpoints" in stats:
            st.subheader("Endpoint Usage")
            endpoint_data = []
            for endpoint, data in stats["endpoints"].items():
                endpoint_data.append({
                    "Endpoint": endpoint,
                    "Requests": data.get("requests", 0),
                    "Avg Response Time": f"{data.get('avg_response_time', 0):.0f}ms",
                    "Success Rate": f"{data.get('success_rate', 0):.1f}%"
                })
            
            df = pd.DataFrame(endpoint_data)
            st.dataframe(df, use_container_width=True)
        
        # Time series data
        if "hourly_requests" in stats:
            st.subheader("Request Volume Over Time")
            hourly_data = stats["hourly_requests"]
            
            # Create a simple time series chart
            df_hourly = pd.DataFrame(hourly_data)
            if not df_hourly.empty:
                fig = px.line(df_hourly, x='hour', y='requests', title='Requests per Hour')
                st.plotly_chart(fig, use_container_width=True)
    
    # Simulated data for demonstration
    else:
        st.subheader("📊 API Usage Overview")
        st.info("API usage tracking is not yet implemented. Here's what it would show:")
        
        # Simulate some data for demonstration
        st.subheader("Simulated Usage Data")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Requests", "1,247")
        with col2:
            st.metric("Catalog Requests", "892")
        with col3:
            st.metric("Suggestions Requests", "355")
        with col4:
            st.metric("Error Rate", "2.3%")
        
        # Simulated endpoint data
        st.subheader("Endpoint Usage")
        endpoint_data = [
            {"Endpoint": "/api/catalog/tools", "Requests": 456, "Avg Response Time": "120ms", "Success Rate": "98.5%"},
            {"Endpoint": "/api/catalog/providers", "Requests": 436, "Avg Response Time": "95ms", "Success Rate": "99.1%"},
            {"Endpoint": "/api/suggestions:generate", "Requests": 355, "Avg Response Time": "2,150ms", "Success Rate": "95.2%"},
            {"Endpoint": "/api/suggestions:multiple", "Requests": 89, "Avg Response Time": "4,200ms", "Success Rate": "92.1%"}
        ]
        
        df = pd.DataFrame(endpoint_data)
        st.dataframe(df, use_container_width=True)
        
        # Simulated time series
        st.subheader("Request Volume Over Time")
        
        # Generate some sample hourly data
        import random
        from datetime import datetime, timedelta
        
        hours = []
        requests = []
        base_time = datetime.now() - timedelta(hours=24)
        
        for i in range(24):
            hour_time = base_time + timedelta(hours=i)
            hours.append(hour_time.strftime("%H:00"))
            # Simulate realistic request patterns
            base_requests = 20 if 9 <= hour_time.hour <= 17 else 5  # Higher during business hours
            requests.append(base_requests + random.randint(-5, 15))
        
        df_hourly = pd.DataFrame({"hour": hours, "requests": requests})
        fig = px.line(df_hourly, x='hour', y='requests', title='Requests per Hour (Last 24 Hours)')
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("💡 To enable real API usage tracking, implement logging in your API server and add a `/api/usage/stats` endpoint.")

def test_api_endpoints(api_base_url: str):
    """Test API endpoints with user-friendly interface."""
    st.subheader("🔧 API Endpoint Tester")
    st.markdown("Test your API endpoints with a user-friendly interface similar to Swagger UI.")
    
    # Create tabs for different endpoint categories
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Catalog", "🔌 Integrations", "💡 Suggestions", "🔍 Search"])
    
    with tab1:
        display_catalog_endpoints(api_base_url)
    
    with tab2:
        display_integrations_endpoints(api_base_url)
    
    with tab3:
        display_suggestions_endpoints(api_base_url)
    
    with tab4:
        display_search_endpoints(api_base_url)

def display_catalog_endpoints(api_base_url: str):
    """Display catalog endpoints with parameters."""
    st.markdown("### 📚 Catalog Endpoints")
    
    # GET /catalog
    with st.expander("📋 GET /catalog - Get Complete Tool Catalog", expanded=True):
        st.markdown("**Description:** Get the complete tool catalog with pagination.")
        st.markdown("**Details:** Returns toolkits with their associated tools (actions and triggers). Supports filtering by category, search terms, and tool availability.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            search = st.text_input("Search", key="catalog_search", placeholder="Search term for toolkit names and descriptions")
            category = st.text_input("Category", key="catalog_category", placeholder="Filter by toolkit category")
            has_actions = st.selectbox("Has Actions", ["", "true", "false"], key="catalog_has_actions")
            has_triggers = st.selectbox("Has Triggers", ["", "true", "false"], key="catalog_has_triggers")
        
        with col2:
            limit = st.number_input("Limit", min_value=1, max_value=100, value=20, key="catalog_limit")
            offset = st.number_input("Offset", min_value=0, value=0, key="catalog_offset")
        
        if st.button("🚀 Execute GET /catalog", type="primary"):
            test_catalog_with_params(api_base_url, search, category, has_actions, has_triggers, limit, offset)
    
    # GET /catalog/tools
    with st.expander("🔧 GET /catalog/tools - List All Tools"):
        st.markdown("**Description:** Get a list of all available tools.")
        
        if st.button("🚀 Execute GET /catalog/tools", type="primary"):
            test_catalog_tools(api_base_url)
    
    # GET /catalog/categories
    with st.expander("🏢 GET /catalog/categories - List Categories"):
        st.markdown("**Description:** Get all available categories.")
        
        if st.button("🚀 Execute GET /catalog/categories", type="primary"):
            test_catalog_providers(api_base_url)
    
    # GET /catalog/tools/{tool_name}
    with st.expander("🔍 GET /catalog/tools/{tool_name} - Get Specific Tool"):
        st.markdown("**Description:** Get details for a specific tool.")
        
        tool_name = st.text_input("Tool Name", key="catalog_tool_name", placeholder="e.g., 'gmail_send_email'")
        
        if st.button("🚀 Execute GET /catalog/tools/{tool_name}", type="primary"):
            if tool_name:
                test_catalog_tool_details(api_base_url, tool_name)
            else:
                st.warning("Please enter a tool name")
    
    # GET /catalog/providers/{provider_slug}
    with st.expander("🏢 GET /catalog/providers/{provider_slug} - Get Provider Details"):
        st.markdown("**Description:** Get details for a specific provider.")
        
        provider_slug = st.text_input("Provider Slug", key="catalog_provider_slug", placeholder="e.g., 'gmail', 'slack'")
        
        if st.button("🚀 Execute GET /catalog/providers/{provider_slug}", type="primary"):
            if provider_slug:
                test_catalog_provider_details(api_base_url, provider_slug)
            else:
                st.warning("Please enter a provider slug")

def display_integrations_endpoints(api_base_url: str):
    """Display integrations endpoints with parameters."""
    st.markdown("### 🔌 Integrations Endpoints")
    
    # GET /api/integrations
    with st.expander("🔍 GET /api/integrations - Get All Integrations", expanded=True):
        st.markdown("**Description:** Get all available integrations.")
        
        if st.button("🚀 Execute GET /api/integrations", type="primary"):
            test_integrations(api_base_url)
    
    # GET /api/integrations/{slug}
    with st.expander("🏢 GET /api/integrations/{slug} - Get Integration Details"):
        st.markdown("**Description:** Get details for a specific integration.")
        
        integration_slug = st.text_input("Integration Slug", key="integration_slug", placeholder="e.g., 'gmail', 'slack'")
        
        if st.button("🚀 Execute GET /api/integrations/{slug}", type="primary"):
            if integration_slug:
                test_integration_details(api_base_url, integration_slug)
            else:
                st.warning("Please enter an integration slug")

def display_suggestions_endpoints(api_base_url: str):
    """Display suggestions endpoints with parameters."""
    st.markdown("### 💡 Suggestions Endpoints")
    
    # POST /api/suggestions:generate
    with st.expander("✨ POST /api/suggestions:generate - Generate Workflow Suggestions", expanded=True):
        st.markdown("**Description:** Generate workflow suggestions based on user input.")
        
        user_request = st.text_area("User Request", key="suggestions_user_request", 
                                  value="I want to send an email to my team about the project update",
                                  height=100, placeholder="Describe what you want to automate")
        
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("User ID", key="suggestions_user_id", value="test_user")
        with col2:
            num_suggestions = st.number_input("Number of Suggestions", min_value=1, max_value=5, value=1, key="suggestions_num")
        
        selected_apps = st.text_input("Selected Apps (comma-separated)", key="suggestions_apps", 
                                    placeholder="e.g., 'gmail,slack' (optional)")
        
        if st.button("🚀 Execute POST /api/suggestions:generate", type="primary"):
            apps_list = [app.strip() for app in selected_apps.split(",")] if selected_apps else None
            test_single_suggestion_with_params(api_base_url, user_request, user_id, num_suggestions, apps_list)
    
    # GET /api/suggestions/{suggestion_id}/preview
    with st.expander("👁️ GET /api/suggestions/{suggestion_id}/preview - Preview Workflow"):
        st.markdown("**Description:** Preview a specific workflow suggestion.")
        
        suggestion_id = st.text_input("Suggestion ID", key="preview_suggestion_id", 
                                    placeholder="e.g., '4dc631e2-212f-4047-9d88-e243821e9d87'")
        
        if st.button("🚀 Execute GET /api/suggestions/{suggestion_id}/preview", type="primary"):
            if suggestion_id:
                test_preview_workflow(api_base_url, suggestion_id)
            else:
                st.warning("Please enter a suggestion ID")
    
    # POST /api/suggestions/{suggestion_id}/actions
    with st.expander("⚡ POST /api/suggestions/{suggestion_id}/actions - Update Actions"):
        st.markdown("**Description:** Update actions for a specific suggestion.")
        
        suggestion_id = st.text_input("Suggestion ID", key="update_suggestion_id", 
                                    placeholder="e.g., '4dc631e2-212f-4047-9d88-e243821e9d87'")
        
        actions_json = st.text_area("Actions JSON", key="update_actions_json",
                                  value='{"actions": [{"id": "action1", "type": "email"}]}',
                                  height=100, placeholder="Enter actions JSON")
        
        if st.button("🚀 Execute POST /api/suggestions/{suggestion_id}/actions", type="primary"):
            if suggestion_id and actions_json:
                test_update_actions(api_base_url, suggestion_id, actions_json)
            else:
                st.warning("Please enter both suggestion ID and actions JSON")
    
    # GET /api/suggestions/analytics
    with st.expander("📊 GET /api/suggestions/analytics - Get Analytics"):
        st.markdown("**Description:** Get analytics for suggestions.")
        
        if st.button("🚀 Execute GET /api/suggestions/analytics", type="primary"):
            test_suggestions_analytics(api_base_url)

def display_search_endpoints(api_base_url: str):
    """Display search endpoints with parameters."""
    st.markdown("### 🔍 Search Endpoints")
    
    # GET /api/integrations/search
    with st.expander("🔍 GET /api/integrations/search - Search Integrations", expanded=True):
        st.markdown("**Description:** Search integrations by query.")
        
        query = st.text_input("Search Query", key="search_query", placeholder="e.g., 'email', 'calendar', 'slack'")
        
        if st.button("🚀 Execute GET /api/integrations/search", type="primary"):
            if query:
                test_integration_search(api_base_url, query)
            else:
                st.warning("Please enter a search query")

def test_catalog_with_params(api_base_url: str, search: str, category: str, has_actions: str, has_triggers: str, limit: int, offset: int):
    """Test the catalog endpoint with parameters."""
    import httpx
    
    try:
        with st.spinner("Fetching catalog with parameters..."):
            with httpx.Client(timeout=10.0) as client:
                params = {}
                if search:
                    params["search"] = search
                if category:
                    params["category"] = category
                if has_actions:
                    params["has_actions"] = has_actions
                if has_triggers:
                    params["has_triggers"] = has_triggers
                if limit:
                    params["limit"] = limit
                if offset:
                    params["offset"] = offset
                
                response = client.get(f"{api_base_url}/catalog", params=params)
                
                if response.status_code == 200:
                    catalog = response.json()
                    st.success("✅ Successfully fetched catalog with parameters")
                    
                    # Display parameters used
                    st.info(f"**Parameters used:** {params}")
                    
                    # Display catalog info
                    if isinstance(catalog, dict):
                        st.json(catalog)
                    else:
                        st.dataframe(pd.DataFrame([catalog]) if not isinstance(catalog, list) else pd.DataFrame(catalog), use_container_width=True)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching catalog: {e}")

def test_catalog(api_base_url: str):
    """Test the full catalog endpoint."""
    import httpx
    
    try:
        with st.spinner("Fetching full catalog..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/catalog")
                
                if response.status_code == 200:
                    catalog = response.json()
                    st.success("✅ Successfully fetched full catalog")
                    
                    # Display catalog info
                    if isinstance(catalog, dict):
                        st.json(catalog)
                    else:
                        st.dataframe(pd.DataFrame([catalog]) if not isinstance(catalog, list) else pd.DataFrame(catalog), use_container_width=True)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching catalog: {e}")

def test_catalog_tools(api_base_url: str):
    """Test the catalog tools endpoint."""
    import httpx
    
    try:
        with st.spinner("Fetching tools from catalog..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/catalog/tools")
                
                if response.status_code == 200:
                    tools = response.json()
                    st.success(f"✅ Successfully fetched {len(tools)} tools")
                    
                    # Display tools in a table
                    if tools:
                        df = pd.DataFrame(tools)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No tools found")
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching tools: {e}")

def test_catalog_providers(api_base_url: str):
    """Test the catalog providers endpoint."""
    import httpx
    
    try:
        with st.spinner("Fetching providers from catalog..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/catalog/categories")
                
                if response.status_code == 200:
                    categories = response.json()
                    st.success(f"✅ Successfully fetched {len(categories)} categories")
                    
                    # Display categories in a table
                    if categories:
                        df = pd.DataFrame(categories)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No categories found")
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching categories: {e}")

def test_integrations(api_base_url: str):
    """Test the integrations endpoint."""
    import httpx
    
    try:
        with st.spinner("Fetching integrations..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/api/integrations")
                
                if response.status_code == 200:
                    integrations = response.json()
                    st.success(f"✅ Successfully fetched {len(integrations)} integrations")
                    
                    # Display integrations in a table
                    if integrations:
                        df = pd.DataFrame(integrations)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No integrations found")
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching integrations: {e}")

def test_catalog_tool_details(api_base_url: str, tool_name: str):
    """Test getting specific tool details."""
    import httpx
    
    try:
        with st.spinner(f"Fetching details for tool: {tool_name}..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/catalog/tools/{tool_name}")
                
                if response.status_code == 200:
                    tool_details = response.json()
                    st.success(f"✅ Successfully fetched details for {tool_name}")
                    st.json(tool_details)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching tool details: {e}")

def test_catalog_provider_details(api_base_url: str, provider_slug: str):
    """Test getting specific provider details."""
    import httpx
    
    try:
        with st.spinner(f"Fetching details for provider: {provider_slug}..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/catalog/providers/{provider_slug}")
                
                if response.status_code == 200:
                    provider_details = response.json()
                    st.success(f"✅ Successfully fetched details for {provider_slug}")
                    st.json(provider_details)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching provider details: {e}")

def test_integration_details(api_base_url: str, integration_slug: str):
    """Test getting integration details."""
    import httpx
    
    try:
        with st.spinner(f"Fetching details for {integration_slug}..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/api/integrations/{integration_slug}")
                
                if response.status_code == 200:
                    details = response.json()
                    st.success(f"✅ Successfully fetched details for {integration_slug}")
                    st.json(details)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching integration details: {e}")

def test_single_suggestion_with_params(api_base_url: str, user_request: str, user_id: str, num_suggestions: int, selected_apps: list = None):
    """Test the suggestion generation endpoint with parameters."""
    import httpx
    
    try:
        with st.spinner("Generating workflow suggestions..."):
            with httpx.Client(timeout=30.0) as client:
                payload = {
                    "user_request": user_request,
                    "user_id": user_id,
                    "num_suggestions": num_suggestions
                }
                if selected_apps:
                    payload["selected_apps"] = selected_apps
                
                response = client.post(f"{api_base_url}/api/suggestions:generate", json=payload)
                
                if response.status_code == 200:
                    suggestions = response.json()
                    st.success("✅ Successfully generated suggestions!")
                    
                    # Display parameters used
                    st.info(f"**Parameters used:** {payload}")
                    
                    # Display the suggestions
                    st.json(suggestions)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error generating suggestions: {e}")

def test_single_suggestion(api_base_url: str):
    """Test the single suggestion generation endpoint."""
    import httpx
    
    # Get user input for the suggestion
    prompt = st.text_area("Enter your prompt for workflow generation:", 
                         value="I want to send an email to my team about the project update",
                         height=100)
    
    if st.button("🚀 Generate Suggestion"):
        try:
            with st.spinner("Generating workflow suggestion..."):
                with httpx.Client(timeout=30.0) as client:
                    payload = {
                        "user_request": prompt,
                        "user_id": "test_user",
                        "num_suggestions": 1
                    }
                    response = client.post(f"{api_base_url}/api/suggestions:generate", json=payload)
                    
                    if response.status_code == 200:
                        suggestion = response.json()
                        st.success("✅ Successfully generated suggestion!")
                        
                        # Display the suggestion
                        st.json(suggestion)
                    else:
                        st.error(f"❌ Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"❌ Error generating suggestion: {e}")

def test_preview_workflow(api_base_url: str, suggestion_id: str):
    """Test the preview workflow endpoint."""
    import httpx
    
    try:
        with st.spinner(f"Previewing workflow {suggestion_id}..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/api/suggestions/{suggestion_id}/preview")
                
                if response.status_code == 200:
                    preview = response.json()
                    st.success("✅ Successfully previewed workflow!")
                    st.json(preview)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error previewing workflow: {e}")

def test_update_actions(api_base_url: str, suggestion_id: str, actions_json: str):
    """Test the update suggestion actions endpoint."""
    import httpx
    
    try:
        with st.spinner(f"Updating actions for {suggestion_id}..."):
            with httpx.Client(timeout=10.0) as client:
                import json
                payload = json.loads(actions_json)
                response = client.post(f"{api_base_url}/api/suggestions/{suggestion_id}/actions", json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    st.success("✅ Successfully updated actions!")
                    st.json(result)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error updating actions: {e}")

def test_suggestions_analytics(api_base_url: str):
    """Test the suggestions analytics endpoint."""
    import httpx
    
    try:
        with st.spinner("Fetching suggestions analytics..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/api/suggestions/analytics")
                
                if response.status_code == 200:
                    analytics = response.json()
                    st.success("✅ Successfully fetched analytics!")
                    st.json(analytics)
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error fetching analytics: {e}")

def test_integration_search(api_base_url: str, query: str):
    """Test integration search with a custom query."""
    import httpx
    
    try:
        with st.spinner(f"Searching for integrations matching '{query}'..."):
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{api_base_url}/api/integrations/search", params={"q": query})
                
                if response.status_code == 200:
                    integrations = response.json()
                    st.success(f"✅ Found {len(integrations)} integrations matching '{query}'")
                    
                    # Display integrations in a table
                    if integrations:
                        df = pd.DataFrame(integrations)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No integrations found matching '{query}'")
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ Error searching integrations: {e}")

def display_api_documentation(api_base_url: str):
    """Display API documentation and available endpoints."""
    st.subheader("📋 API Documentation")
    
    st.markdown("""
    ### Available Endpoints
    
    #### System Endpoints
    - `GET /health` - Health check
    - `GET /api/usage/stats` - Usage statistics
    
    #### Catalog Endpoints
    - `GET /catalog` - Get full catalog
    - `GET /catalog/tools` - List all tools
    - `GET /catalog/tools/{tool_name}` - Get specific tool
    - `GET /catalog/providers/{provider_slug}` - Get specific provider
    - `GET /catalog/categories` - Get all categories
    
    #### Integrations Endpoints
    - `GET /api/integrations` - Get all integrations
    - `GET /api/integrations/search?q={query}` - Search integrations
    - `GET /api/integrations/{slug}` - Get integration details
    
    #### Suggestions Endpoints
    - `POST /api/suggestions:generate` - Generate workflow suggestions
    - `GET /api/suggestions/{suggestion_id}/preview` - Preview workflow
    - `POST /api/suggestions/{suggestion_id}/actions` - Update suggestion actions
    - `GET /api/suggestions/analytics` - Get suggestions analytics
    
    #### Request Examples
    
    **Generate Suggestions:**
    ```json
    POST /api/suggestions:generate
    {
        "user_request": "I want to send an email to my team",
        "user_id": "user123",
        "num_suggestions": 1
    }
    ```
    
    **Preview Workflow:**
    ```
    GET /api/suggestions/{suggestion_id}/preview
    ```
    
    **Update Actions:**
    ```json
    POST /api/suggestions/{suggestion_id}/actions
    {
        "actions": [{"id": "action1", "type": "email"}]
    }
    ```
    
    **Get Catalog Tools:**
    ```
    GET /catalog/tools
    ```
    
    **Search Integrations:**
    ```
    GET /api/integrations/search?q=email
    ```
    """)
    
    # Link to interactive docs
    st.markdown(f"""
    ### Interactive Documentation
    - **Swagger UI**: [{api_base_url}/docs]({api_base_url}/docs)
    - **ReDoc**: [{api_base_url}/redoc]({api_base_url}/redoc)
    """)

def settings_page():
    """Settings page."""
    st.header("Settings")
    
    st.subheader("Environment Variables")
    
    # Check required environment variables
    required_vars = {
        "ANTHROPIC_API_KEY": "Anthropic API key for AI generation",
        "GROQ_API_KEY": "Groq API key for AI generation",
        "API_PORT": "Port for API server (default: 8001)"
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            st.success(f"✅ {var}: {'*' * len(value)}")
        else:
            st.error(f"❌ {var}: Not set")
        st.caption(description)
    
    st.subheader("API Configuration")
    api_base_url = st.text_input("API Base URL", value="http://localhost:8001")
    
    st.subheader("About")
    st.info("""
    This is the evaluation dashboard for the Workflow Automation Engine.
    
    **Features:**
    - Run evaluations locally or via API
    - View detailed results and metrics
    - Manage test cases
    - Historical report analysis
    - API usage tracking
    
    **Usage:**
    1. Ensure your environment variables are set
    2. For API-based evaluation, make sure the API server is running
    3. Select test cases and run evaluation
    4. View results and download reports
    5. Monitor API usage and performance
    """)

if __name__ == "__main__":
    main()
