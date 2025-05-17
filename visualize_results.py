#!/usr/bin/env python3
"""
Visualization tool for cognitive agent network simulation results.

This script generates various plots to analyze simulation results, focusing on 
cognitive resonance metrics (RCAN), progress rates (P_rate), and communication 
cost rates (C_rate) comparing baseline and hybrid agent configurations.
"""

import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set up Seaborn style for better-looking plots with larger labels
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 24,  # Doubled from 12 to 24
    'axes.labelsize': 24,
    'axes.titlesize': 24,
    'xtick.labelsize': 24,
    'ytick.labelsize': 24,
    'legend.fontsize': 24,
    'figure.titlesize': 24
})


def load_results(csv_path):
    """
    Load simulation results from CSV file into a pandas DataFrame.
    
    Args:
        csv_path (str): Path to the results CSV file
    
    Returns:
        pd.DataFrame: DataFrame containing simulation results
    """
    try:
        df = pd.read_csv(csv_path)
        
        # Check if the new metrics are in the DataFrame
        required_columns = [
            'baseline_P_rate', 'hybrid_P_rate', 
            'baseline_C_rate', 'hybrid_C_rate',
            'baseline_R_CAN', 'hybrid_R_CAN'
        ]
        
        # If metrics are missing, add placeholder columns with NaN values
        for col in required_columns:
            if col not in df.columns:
                print(f"Warning: Column '{col}' not found in results. "
                      "Adding placeholder column with NaN values.")
                df[col] = np.nan
        
        return df
    except Exception as e:
        print(f"Error loading results file: {e}")
        raise


def create_output_dir(output_dir):
    """
    Create output directory for plots if it doesn't exist.
    
    Args:
        output_dir (str): Path to output directory
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print(f"Output directory created/verified: {output_dir}")


def plot_rcan_comparison(df, output_dir):
    """
    Create bar chart comparing baseline and hybrid RCAN values.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plot
    """
    plt.figure(figsize=(20, 12))
    
    # Calculate mean and standard error for baseline and hybrid RCAN
    rcan_data = pd.DataFrame({
        'Configuration': ['Baseline', 'Hybrid'],
        'Mean RCAN': [df['baseline_R_CAN'].mean(), df['hybrid_R_CAN'].mean()],
        'SE': [df['baseline_R_CAN'].sem(), df['hybrid_R_CAN'].sem()]
    })
    
    # Create bar chart
    ax = sns.barplot(x='Configuration', y='Mean RCAN', hue='Configuration', data=rcan_data, 
                    palette=['blue', 'orange'], legend=False)
    
    # Add error bars
    ax.errorbar(x=rcan_data.index, y=rcan_data['Mean RCAN'], 
               yerr=rcan_data['SE'], fmt='none', c='black', capsize=5)
    
    plt.title('Average Cognitive Resonance: Baseline vs. Hybrid')
    plt.ylabel('Average RCAN')
    plt.tight_layout()
    
    # Save plot
    output_path = os.path.join(output_dir, 'rcan_comparison_bar.png')
    plt.savefig(output_path, dpi=600)
    plt.close()
    print(f"Saved plot to {output_path}")


def plot_progress_vs_cost(df, output_dir):
    """
    Create scatter plot of Progress Rate vs Communication Cost Rate.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plot
    """
    plt.figure(figsize=(20, 16))
    
    # Check if we need log scale (if data spans several orders of magnitude)
    baseline_c_range = df['baseline_C_rate'].max() / (df['baseline_C_rate'].min() or 1)
    hybrid_c_range = df['hybrid_C_rate'].max() / (df['hybrid_C_rate'].min() or 1)
    baseline_p_range = df['baseline_P_rate'].max() / (df['baseline_P_rate'].min() or 1)
    hybrid_p_range = df['hybrid_P_rate'].max() / (df['hybrid_P_rate'].min() or 1)
    
    use_log_x = (baseline_c_range > 100) or (hybrid_c_range > 100)
    use_log_y = (baseline_p_range > 100) or (hybrid_p_range > 100)
    
    # Plot baseline points
    plt.scatter(df['baseline_C_rate'], df['baseline_P_rate'], 
                label='Baseline', alpha=0.7, s=50, color='blue')
    
    # Plot hybrid points
    plt.scatter(df['hybrid_C_rate'], df['hybrid_P_rate'], 
                label='Hybrid', alpha=0.7, s=50, color='orange')
    
    # Add labels and title
    plt.xlabel('Communication Cost Rate (C_rate)')
    plt.ylabel('Progress Rate (P_rate)')
    plt.title('Progress Rate vs. Communication Cost Rate')
    
    # Apply log scale if needed
    if use_log_x:
        plt.xscale('log')
    if use_log_y:
        plt.yscale('log')
    
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save plot
    output_path = os.path.join(output_dir, 'p_rate_vs_c_rate_scatter.png')
    plt.savefig(output_path, dpi=600)
    plt.close()
    print(f"Saved plot to {output_path}")


def plot_metric_comparison_scatter(df, output_dir):
    """
    Create scatter plots comparing baseline vs hybrid for key metrics.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plots
    """
    # Define metrics to compare
    metrics = [
        ('time', 'Time to Solution (seconds)', True),  # (name, label, log_scale)
        ('bytes', 'Communication Volume (bytes)', True),
        ('P_rate', 'Progress Rate', False),
        ('C_rate', 'Communication Cost Rate', False),
        ('R_CAN', 'Cognitive Resonance', False)
    ]
    
    for metric_name, metric_label, use_log in metrics:
        baseline_col = f'baseline_{metric_name}'
        hybrid_col = f'hybrid_{metric_name}'
        
        # Filter out rows where either baseline or hybrid metric is missing
        if metric_name == 'time':
            # For time, only include successful runs
            valid_df = df[(df['baseline_success_rate'] > 0) & (df['hybrid_success_rate'] > 0)]
            valid_df = valid_df[valid_df[baseline_col].notna() & valid_df[hybrid_col].notna()]
        else:
            valid_df = df[df[baseline_col].notna() & df[hybrid_col].notna()]
        
        if len(valid_df) == 0:
            print(f"Warning: No valid data for {metric_name} comparison")
            continue
            
        plt.figure(figsize=(16, 16))
        
        # Get min and max values for axis limits
        min_val = min(valid_df[baseline_col].min(), valid_df[hybrid_col].min())
        max_val = max(valid_df[baseline_col].max(), valid_df[hybrid_col].max())
        
        # Add some padding to axis limits
        padding = (max_val - min_val) * 0.1
        min_val = max(0, min_val - padding)
        max_val = max_val + padding
        
        # Plot scatter points
        plt.scatter(valid_df[baseline_col], valid_df[hybrid_col], 
                    alpha=0.7, s=50, color='purple')
        
        # Plot reference line y=x
        plt.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5)
        
        # Labels and title
        plt.xlabel(f'Baseline {metric_label}')
        plt.ylabel(f'Hybrid {metric_label}')
        plt.title(f'Hybrid vs. Baseline: {metric_label}')
        
        # Apply log scale if specified
        if use_log:
            plt.xscale('log')
            plt.yscale('log')
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot
        output_path = os.path.join(output_dir, f'{metric_name}_comparison_scatter.png')
        plt.savefig(output_path, dpi=600)
        plt.close()
        print(f"Saved plot to {output_path}")


def plot_ecdf(df, output_dir):
    """
    Create ECDF plots for key metrics with baseline and hybrid overlaid.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plots
    """
    # Define metrics for ECDF plots
    metrics = [
        ('time', 'Time to Solution (seconds)', True),  # (name, label, log_scale)
        ('bytes', 'Communication Volume (bytes)', True),
        ('P_rate', 'Progress Rate', False),
        ('C_rate', 'Communication Cost Rate', False),
        ('R_CAN', 'Cognitive Resonance', False)
    ]
    
    for metric_name, metric_label, use_log in metrics:
        baseline_col = f'baseline_{metric_name}'
        hybrid_col = f'hybrid_{metric_name}'
        
        plt.figure(figsize=(20, 12))
        
        # For time, only include successful runs
        if metric_name == 'time':
            baseline_data = df[df['baseline_success_rate'] > 0][baseline_col].dropna()
            hybrid_data = df[df['hybrid_success_rate'] > 0][hybrid_col].dropna()
        else:
            baseline_data = df[baseline_col].dropna()
            hybrid_data = df[hybrid_col].dropna()
        
        # Plot ECDF for baseline
        if len(baseline_data) > 0:
            sns.ecdfplot(baseline_data, label='Baseline', color='blue')
        
        # Plot ECDF for hybrid
        if len(hybrid_data) > 0:
            sns.ecdfplot(hybrid_data, label='Hybrid', color='orange')
        
        # Labels and title
        plt.xlabel(metric_label)
        plt.ylabel('Cumulative Probability')
        plt.title(f'ECDF of {metric_label}')
        
        # Apply log scale if specified
        if use_log:
            plt.xscale('log')
        
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot
        output_path = os.path.join(output_dir, f'{metric_name}_ecdf.png')
        plt.savefig(output_path, dpi=600)
        plt.close()
        print(f"Saved plot to {output_path}")


def plot_force_semantic_impact(df, output_dir):
    """
    Create grouped bar chart showing impact of generator.force_semantic on RCAN.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plot
    """
    # Check if generator.force_semantic column exists
    if 'generator.force_semantic' not in df.columns:
        print("Warning: 'generator.force_semantic' column not found. Skipping force semantic impact plot.")
        return
        
    plt.figure(figsize=(10, 6))
    
    # Group by force_semantic and calculate mean and standard error
    grouped = df.groupby('generator.force_semantic')
    
    # Prepare data for plotting
    force_semantic_values = []
    baseline_means = []
    hybrid_means = []
    baseline_errors = []
    hybrid_errors = []
    
    for name, group in grouped:
        force_semantic_values.append(str(name))
        baseline_means.append(group['baseline_R_CAN'].mean())
        hybrid_means.append(group['hybrid_R_CAN'].mean())
        baseline_errors.append(group['baseline_R_CAN'].sem())
        hybrid_errors.append(group['hybrid_R_CAN'].sem())
    
    # Set up bar positions
    x = np.arange(len(force_semantic_values))
    width = 0.35
    
    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(20, 12))
    baseline_bars = ax.bar(x - width/2, baseline_means, width, label='Baseline', color='blue', yerr=baseline_errors, capsize=5)
    hybrid_bars = ax.bar(x + width/2, hybrid_means, width, label='Hybrid', color='orange', yerr=hybrid_errors, capsize=5)
    
    # Add labels and title
    ax.set_xlabel('generator.force_semantic')
    ax.set_ylabel('Average RCAN')
    ax.set_title('Impact of Forced Semantic Hint on Cognitive Resonance')
    ax.set_xticks(x)
    ax.set_xticklabels(force_semantic_values)
    ax.legend()
    
    # Add value labels on top of bars
    def add_labels(bars):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.4f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=18)
    
    add_labels(baseline_bars)
    add_labels(hybrid_bars)
    
    plt.tight_layout()
    
    # Save plot
    output_path = os.path.join(output_dir, 'rcan_by_force_semantic.png')
    plt.savefig(output_path, dpi=600)
    plt.close()
    print(f"Saved plot to {output_path}")


def plot_lifetime_impact(df, output_dir):
    """
    Create line chart showing impact of synthetic_human.lifetime on Hybrid RCAN.
    
    Args:
        df (pd.DataFrame): DataFrame containing simulation results
        output_dir (str): Directory to save the plot
    """
    # Check if synthetic_human.lifetime column exists
    if 'synthetic_human.lifetime' not in df.columns:
        print("Warning: 'synthetic_human.lifetime' column not found. Skipping lifetime impact plots.")
        return
    
    plt.figure(figsize=(20, 12))
    
    # Group by lifetime and calculate mean and standard error
    grouped = df.groupby('synthetic_human.lifetime')
    
    # Prepare data for plotting
    lifetimes = []
    hybrid_rcan_means = []
    hybrid_rcan_errors = []
    
    for name, group in grouped:
        lifetimes.append(name)
        hybrid_rcan_means.append(group['hybrid_R_CAN'].mean())
        hybrid_rcan_errors.append(group['hybrid_R_CAN'].sem())
    
    # Sort by lifetime
    sorted_indices = np.argsort(lifetimes)
    lifetimes = [lifetimes[i] for i in sorted_indices]
    hybrid_rcan_means = [hybrid_rcan_means[i] for i in sorted_indices]
    hybrid_rcan_errors = [hybrid_rcan_errors[i] for i in sorted_indices]
    
    # Check if we have enough unique values for a line plot
    if len(lifetimes) >= 2:
        # Create line plot
        plt.errorbar(lifetimes, hybrid_rcan_means, yerr=hybrid_rcan_errors, 
                    marker='o', linestyle='-', color='orange', capsize=5)
    else:
        # Create bar chart if only one value
        plt.bar(lifetimes, hybrid_rcan_means, yerr=hybrid_rcan_errors, 
               color='orange', capsize=5)
    
    # Add labels and title
    plt.xlabel('synthetic_human.lifetime')
    plt.ylabel('Average Hybrid RCAN')
    plt.title('Impact of Human Agent Lifetime on Hybrid Cognitive Resonance')
    plt.grid(True, alpha=0.3)
    
    # Add data points as text labels
    for i in range(len(lifetimes)):
        plt.annotate(f'{hybrid_rcan_means[i]:.4f}',
                    xy=(lifetimes[i], hybrid_rcan_means[i]),
                    xytext=(5, 5),  # 5 points offset
                    textcoords="offset points",
                    fontsize=18)
    
    plt.tight_layout()
    
    # Save plot
    output_path = os.path.join(output_dir, 'hybrid_rcan_by_lifetime.png')
    plt.savefig(output_path, dpi=600)
    plt.close()
    print(f"Saved plot to {output_path}")
    
    # Optional: Create similar plots for P_rate and C_rate
    metrics = [
        ('P_rate', 'Progress Rate'),
        ('C_rate', 'Communication Cost Rate')
    ]
    
    for metric_name, metric_label in metrics:
        plt.figure(figsize=(20, 12))
        hybrid_metric_col = f'hybrid_{metric_name}'
        
        # Group by lifetime and calculate mean and standard error
        grouped = df.groupby('synthetic_human.lifetime')
        
        # Prepare data for plotting
        lifetimes = []
        hybrid_metric_means = []
        hybrid_metric_errors = []
        
        for name, group in grouped:
            lifetimes.append(name)
            hybrid_metric_means.append(group[hybrid_metric_col].mean())
            hybrid_metric_errors.append(group[hybrid_metric_col].sem())
        
        # Sort by lifetime
        sorted_indices = np.argsort(lifetimes)
        lifetimes = [lifetimes[i] for i in sorted_indices]
        hybrid_metric_means = [hybrid_metric_means[i] for i in sorted_indices]
        hybrid_metric_errors = [hybrid_metric_errors[i] for i in sorted_indices]
        
        # Check if we have enough unique values for a line plot
        if len(lifetimes) >= 2:
            # Create line plot
            plt.errorbar(lifetimes, hybrid_metric_means, yerr=hybrid_metric_errors, 
                        marker='o', linestyle='-', color='orange', capsize=5)
        else:
            # Create bar chart if only one value
            plt.bar(lifetimes, hybrid_metric_means, yerr=hybrid_metric_errors, 
                   color='orange', capsize=5)
        
        # Add labels and title
        plt.xlabel('synthetic_human.lifetime')
        plt.ylabel(f'Average Hybrid {metric_label}')
        plt.title(f'Impact of Human Agent Lifetime on Hybrid {metric_label}')
        plt.grid(True, alpha=0.3)
        
        # Add data points as text labels
        for i in range(len(lifetimes)):
            plt.annotate(f'{hybrid_metric_means[i]:.4f}',
                        xy=(lifetimes[i], hybrid_metric_means[i]),
                        xytext=(5, 5),  # 5 points offset
                        textcoords="offset points",
                        fontsize=18)
        
        plt.tight_layout()
        
        # Save plot
        output_path = os.path.join(output_dir, f'hybrid_{metric_name.lower()}_by_lifetime.png')
        plt.savefig(output_path, dpi=600)
        plt.close()
        print(f"Saved plot to {output_path}")


def main():
    """
    Main function to process command-line arguments and generate plots.
    """
    parser = argparse.ArgumentParser(description='Generate plots from simulation results')
    parser.add_argument('--input', '-i', type=str, default='results.csv',
                       help='Path to input CSV file (default: results.csv)')
    parser.add_argument('--output', '-o', type=str, default='plots',
                       help='Directory to save output plots (default: plots)')
    args = parser.parse_args()
    
    # Create output directory
    create_output_dir(args.output)
    
    # Load results
    print(f"Loading results from {args.input}...")
    df = load_results(args.input)
    print(f"Loaded {len(df)} simulation results.")
    
    # Generate plots
    print("Generating plots...")
    plot_rcan_comparison(df, args.output)
    plot_progress_vs_cost(df, args.output)
    plot_metric_comparison_scatter(df, args.output)
    plot_ecdf(df, args.output)
    plot_force_semantic_impact(df, args.output)
    plot_lifetime_impact(df, args.output)
    
    print(f"All plots saved to {args.output} directory.")


if __name__ == "__main__":
    main()