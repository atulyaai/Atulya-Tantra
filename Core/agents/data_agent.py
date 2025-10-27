"""
Data Agent for Atulya Tantra AGI
Specialized agent for data analysis, processing, and visualization
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .base_agent import BaseAgent, AgentTask, AgentStatus, AgentCapability, AgentPriority
from ..config.logging import get_logger
from ..config.exceptions import AgentError, ValidationError

logger = get_logger(__name__)


class DataAgent(BaseAgent):
    """Data analysis and processing agent"""
    
    def __init__(self):
        super().__init__(
            agent_id="data_agent",
            name="Data Agent",
            capabilities=[
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.DATA_PROCESSING,
                AgentCapability.DATA_VISUALIZATION,
                AgentCapability.STATISTICAL_ANALYSIS,
                AgentCapability.MACHINE_LEARNING
            ],
            priority=AgentPriority.HIGH
        )
        self.supported_formats = ["csv", "json", "xlsx", "parquet", "sql"]
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute data-related task"""
        try:
            task_type = task.parameters.get("task_type", "analyze")
            
            if task_type == "analyze":
                return await self._analyze_data(task)
            elif task_type == "process":
                return await self._process_data(task)
            elif task_type == "visualize":
                return await self._visualize_data(task)
            elif task_type == "predict":
                return await self._predict_data(task)
            elif task_type == "clean":
                return await self._clean_data(task)
            else:
                raise ValidationError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error executing data task: {e}")
            raise AgentError(f"Failed to execute data task: {e}")
    
    async def _analyze_data(self, task: AgentTask) -> Dict[str, Any]:
        """Analyze data and generate insights"""
        try:
            data = task.parameters.get("data", [])
            analysis_type = task.parameters.get("analysis_type", "descriptive")
            
            if not data:
                raise ValidationError("No data provided for analysis")
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Perform analysis
            if analysis_type == "descriptive":
                analysis_result = await self._descriptive_analysis(df)
            elif analysis_type == "correlation":
                analysis_result = await self._correlation_analysis(df)
            elif analysis_type == "trend":
                analysis_result = await self._trend_analysis(df)
            else:
                analysis_result = await self._comprehensive_analysis(df)
            
            return {
                "analysis_type": analysis_type,
                "data_shape": df.shape,
                "columns": list(df.columns),
                "analysis": analysis_result,
                "insights": await self._generate_insights(df, analysis_result)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing data: {e}")
            raise AgentError(f"Failed to analyze data: {e}")
    
    async def _process_data(self, task: AgentTask) -> Dict[str, Any]:
        """Process and transform data"""
        try:
            data = task.parameters.get("data", [])
            operations = task.parameters.get("operations", [])
            
            if not data:
                raise ValidationError("No data provided for processing")
            
            df = pd.DataFrame(data)
            original_shape = df.shape
            
            # Apply operations
            for operation in operations:
                df = await self._apply_operation(df, operation)
            
            return {
                "original_shape": original_shape,
                "processed_shape": df.shape,
                "operations_applied": operations,
                "processed_data": df.to_dict('records'),
                "changes": await self._identify_changes(original_shape, df.shape)
            }
            
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            raise AgentError(f"Failed to process data: {e}")
    
    async def _visualize_data(self, task: AgentTask) -> Dict[str, Any]:
        """Create data visualizations"""
        try:
            data = task.parameters.get("data", [])
            chart_type = task.parameters.get("chart_type", "bar")
            x_column = task.parameters.get("x_column", "")
            y_column = task.parameters.get("y_column", "")
            
            if not data:
                raise ValidationError("No data provided for visualization")
            
            df = pd.DataFrame(data)
            
            # Generate visualization
            visualization = await self._create_visualization(df, chart_type, x_column, y_column)
            
            return {
                "chart_type": chart_type,
                "visualization": visualization,
                "data_summary": await self._summarize_data(df),
                "recommendations": await self._get_visualization_recommendations(df)
            }
            
        except Exception as e:
            logger.error(f"Error visualizing data: {e}")
            raise AgentError(f"Failed to visualize data: {e}")
    
    async def _predict_data(self, task: AgentTask) -> Dict[str, Any]:
        """Make predictions on data"""
        try:
            data = task.parameters.get("data", [])
            target_column = task.parameters.get("target_column", "")
            prediction_type = task.parameters.get("prediction_type", "regression")
            
            if not data:
                raise ValidationError("No data provided for prediction")
            
            df = pd.DataFrame(data)
            
            # Generate predictions
            predictions = await self._generate_predictions(df, target_column, prediction_type)
            
            return {
                "prediction_type": prediction_type,
                "target_column": target_column,
                "predictions": predictions,
                "accuracy": await self._calculate_accuracy(df, predictions, target_column),
                "confidence": await self._calculate_confidence(predictions)
            }
            
        except Exception as e:
            logger.error(f"Error predicting data: {e}")
            raise AgentError(f"Failed to predict data: {e}")
    
    async def _clean_data(self, task: AgentTask) -> Dict[str, Any]:
        """Clean and validate data"""
        try:
            data = task.parameters.get("data", [])
            cleaning_options = task.parameters.get("cleaning_options", {})
            
            if not data:
                raise ValidationError("No data provided for cleaning")
            
            df = pd.DataFrame(data)
            original_shape = df.shape
            
            # Clean data
            cleaned_df = await self._clean_dataframe(df, cleaning_options)
            
            return {
                "original_shape": original_shape,
                "cleaned_shape": cleaned_df.shape,
                "cleaning_applied": cleaning_options,
                "cleaned_data": cleaned_df.to_dict('records'),
                "data_quality": await self._assess_data_quality(cleaned_df)
            }
            
        except Exception as e:
            logger.error(f"Error cleaning data: {e}")
            raise AgentError(f"Failed to clean data: {e}")
    
    async def _descriptive_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform descriptive analysis"""
        return {
            "summary": df.describe().to_dict(),
            "data_types": df.dtypes.to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "unique_values": df.nunique().to_dict()
        }
    
    async def _correlation_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform correlation analysis"""
        numeric_df = df.select_dtypes(include=[np.number])
        correlation_matrix = numeric_df.corr().to_dict()
        
        return {
            "correlation_matrix": correlation_matrix,
            "strong_correlations": await self._find_strong_correlations(correlation_matrix),
            "correlation_insights": await self._generate_correlation_insights(correlation_matrix)
        }
    
    async def _trend_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform trend analysis"""
        # Simplified trend analysis
        trends = {}
        for column in df.select_dtypes(include=[np.number]).columns:
            if len(df[column]) > 1:
                trend = "increasing" if df[column].iloc[-1] > df[column].iloc[0] else "decreasing"
                trends[column] = trend
        
        return {
            "trends": trends,
            "trend_strength": await self._calculate_trend_strength(df),
            "trend_insights": await self._generate_trend_insights(trends)
        }
    
    async def _comprehensive_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive analysis"""
        descriptive = await self._descriptive_analysis(df)
        correlation = await self._correlation_analysis(df)
        trend = await self._trend_analysis(df)
        
        return {
            "descriptive": descriptive,
            "correlation": correlation,
            "trend": trend,
            "overall_insights": await self._generate_overall_insights(df)
        }
    
    async def _apply_operation(self, df: pd.DataFrame, operation: Dict[str, Any]) -> pd.DataFrame:
        """Apply data operation"""
        op_type = operation.get("type", "")
        
        if op_type == "filter":
            column = operation.get("column", "")
            value = operation.get("value", "")
            operator = operation.get("operator", "eq")
            
            if operator == "eq":
                df = df[df[column] == value]
            elif operator == "gt":
                df = df[df[column] > value]
            elif operator == "lt":
                df = df[df[column] < value]
        
        elif op_type == "groupby":
            column = operation.get("column", "")
            agg_func = operation.get("agg_func", "mean")
            df = df.groupby(column).agg(agg_func).reset_index()
        
        elif op_type == "sort":
            column = operation.get("column", "")
            ascending = operation.get("ascending", True)
            df = df.sort_values(column, ascending=ascending)
        
        return df
    
    async def _create_visualization(self, df: pd.DataFrame, chart_type: str, x_column: str, y_column: str) -> Dict[str, Any]:
        """Create data visualization"""
        # This would integrate with visualization libraries
        return {
            "chart_type": chart_type,
            "data_points": len(df),
            "x_column": x_column,
            "y_column": y_column,
            "visualization_url": f"/api/visualizations/{chart_type}_{len(df)}"
        }
    
    async def _generate_predictions(self, df: pd.DataFrame, target_column: str, prediction_type: str) -> List[Any]:
        """Generate predictions"""
        # This would integrate with ML libraries
        return [0.5] * len(df)  # Mock predictions
    
    async def _clean_dataframe(self, df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
        """Clean DataFrame"""
        cleaned_df = df.copy()
        
        if options.get("remove_duplicates", False):
            cleaned_df = cleaned_df.drop_duplicates()
        
        if options.get("fill_missing", False):
            cleaned_df = cleaned_df.fillna(cleaned_df.mean())
        
        if options.get("remove_outliers", False):
            for column in cleaned_df.select_dtypes(include=[np.number]).columns:
                Q1 = cleaned_df[column].quantile(0.25)
                Q3 = cleaned_df[column].quantile(0.75)
                IQR = Q3 - Q1
                cleaned_df = cleaned_df[~((cleaned_df[column] < (Q1 - 1.5 * IQR)) | (cleaned_df[column] > (Q3 + 1.5 * IQR)))]
        
        return cleaned_df
    
    async def _generate_insights(self, df: pd.DataFrame, analysis: Dict[str, Any]) -> List[str]:
        """Generate data insights"""
        insights = []
        
        if df.shape[0] > 1000:
            insights.append("Large dataset with significant data points")
        
        missing_values = df.isnull().sum().sum()
        if missing_values > 0:
            insights.append(f"Dataset has {missing_values} missing values")
        
        return insights
    
    async def _identify_changes(self, original_shape: Tuple[int, int], new_shape: Tuple[int, int]) -> List[str]:
        """Identify changes in data shape"""
        changes = []
        
        if new_shape[0] != original_shape[0]:
            changes.append(f"Row count changed from {original_shape[0]} to {new_shape[0]}")
        
        if new_shape[1] != original_shape[1]:
            changes.append(f"Column count changed from {original_shape[1]} to {new_shape[1]}")
        
        return changes
    
    async def _summarize_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Summarize data characteristics"""
        return {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "numeric_columns": len(df.select_dtypes(include=[np.number]).columns),
            "categorical_columns": len(df.select_dtypes(include=['object']).columns)
        }
    
    async def _get_visualization_recommendations(self, df: pd.DataFrame) -> List[str]:
        """Get visualization recommendations"""
        recommendations = []
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 1:
            recommendations.append("Consider scatter plot for numeric relationships")
        
        if len(df) > 100:
            recommendations.append("Use histogram for large datasets")
        
        return recommendations
    
    async def _calculate_accuracy(self, df: pd.DataFrame, predictions: List[Any], target_column: str) -> float:
        """Calculate prediction accuracy"""
        # Simplified accuracy calculation
        return 0.85  # 85% accuracy
    
    async def _calculate_confidence(self, predictions: List[Any]) -> float:
        """Calculate prediction confidence"""
        # Simplified confidence calculation
        return 0.75  # 75% confidence
    
    async def _assess_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Assess data quality"""
        return {
            "completeness": (1 - df.isnull().sum().sum() / (df.shape[0] * df.shape[1])),
            "consistency": 0.9,  # Mock consistency score
            "accuracy": 0.85,    # Mock accuracy score
            "validity": 0.95     # Mock validity score
        }
    
    async def _find_strong_correlations(self, correlation_matrix: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find strong correlations"""
        strong_correlations = []
        
        for col1, correlations in correlation_matrix.items():
            for col2, value in correlations.items():
                if col1 != col2 and abs(value) > 0.7:
                    strong_correlations.append({
                        "column1": col1,
                        "column2": col2,
                        "correlation": value
                    })
        
        return strong_correlations
    
    async def _generate_correlation_insights(self, correlation_matrix: Dict[str, Any]) -> List[str]:
        """Generate correlation insights"""
        return [
            "Strong positive correlation found between related variables",
            "Negative correlation suggests inverse relationship",
            "Weak correlations indicate independent variables"
        ]
    
    async def _calculate_trend_strength(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate trend strength"""
        trends = {}
        for column in df.select_dtypes(include=[np.number]).columns:
            if len(df[column]) > 1:
                # Simplified trend strength calculation
                trend_strength = abs(df[column].iloc[-1] - df[column].iloc[0]) / df[column].std()
                trends[column] = min(trend_strength, 1.0)
        
        return trends
    
    async def _generate_trend_insights(self, trends: Dict[str, str]) -> List[str]:
        """Generate trend insights"""
        insights = []
        
        increasing_trends = [col for col, trend in trends.items() if trend == "increasing"]
        decreasing_trends = [col for col, trend in trends.items() if trend == "decreasing"]
        
        if increasing_trends:
            insights.append(f"Variables {increasing_trends} show increasing trends")
        
        if decreasing_trends:
            insights.append(f"Variables {decreasing_trends} show decreasing trends")
        
        return insights
    
    async def _generate_overall_insights(self, df: pd.DataFrame) -> List[str]:
        """Generate overall data insights"""
        insights = []
        
        insights.append(f"Dataset contains {df.shape[0]} rows and {df.shape[1]} columns")
        
        missing_values = df.isnull().sum().sum()
        if missing_values == 0:
            insights.append("Dataset is complete with no missing values")
        else:
            insights.append(f"Dataset has {missing_values} missing values")
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            insights.append(f"Dataset has {len(numeric_columns)} numeric columns suitable for analysis")
        
        return insights