<script lang="ts">
  interface RawResult {
    validation_id: string;
    model_name: string;
    embedding_provider: string;
    with_context: boolean;
    image_url: string;
    real_question: string;
    crowd_majority: string;
    similar_images: any[];
    prompt_used: string;
    llm_response: string;
    error: string | null;
    processing_time: number;
  }

  interface GroupedResult {
    id: string;
    validation_id: string;
    model_name: string;
    embedding_provider: string;
    image_url: string;
    real_question: string;
    crowd_majority: string;
    with_context: RawResult | null;
    without_context: RawResult | null;
  }

  // Props
  let { data = [] }: { data: GroupedResult[] } = $props();

  // Get evaluations from sessionStorage
  function getEvaluations() {
    if (typeof sessionStorage === "undefined") return {};
    try {
      const stored = sessionStorage.getItem("llm-evaluations");
      return stored ? JSON.parse(stored) : {};
    } catch (e) {
      return {};
    }
  }

  // Convert evaluation to numeric score
  function getNumericScore(evaluation: string | null): number | null {
    switch (evaluation) {
      case "directly_answered":
        return 3;
      case "inferable":
        return 2;
      case "missing_incorrect":
        return 1;
      case "hallucination":
        return 0;
      default:
        return null;
    }
  }

  // Calculate model performance metrics
  function calculateModelMetrics() {
    const evaluations = getEvaluations();
    const modelStats: Record<
      string,
      {
        withContext: number[];
        withoutContext: number[];
        contextImpact: number[];
        totalEvaluated: number;
      }
    > = {};

    data.forEach((result) => {
      if (!modelStats[result.model_name]) {
        modelStats[result.model_name] = {
          withContext: [],
          withoutContext: [],
          contextImpact: [],
          totalEvaluated: 0,
        };
      }

      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = getNumericScore(evaluations[withKey]);
      const withoutEval = getNumericScore(evaluations[withoutKey]);

      if (withEval !== null) {
        modelStats[result.model_name].withContext.push(withEval);
        modelStats[result.model_name].totalEvaluated++;
      }
      if (withoutEval !== null) {
        modelStats[result.model_name].withoutContext.push(withoutEval);
        modelStats[result.model_name].totalEvaluated++;
      }
      if (withEval !== null && withoutEval !== null) {
        modelStats[result.model_name].contextImpact.push(
          withEval - withoutEval
        );
      }
    });

    return modelStats;
  }

  // Calculate embedding provider metrics
  function calculateEmbeddingMetrics() {
    const evaluations = getEvaluations();
    const embeddingStats: Record<
      string,
      {
        withContext: number[];
        withoutContext: number[];
        totalEvaluated: number;
      }
    > = {};

    data.forEach((result) => {
      if (!embeddingStats[result.embedding_provider]) {
        embeddingStats[result.embedding_provider] = {
          withContext: [],
          withoutContext: [],
          totalEvaluated: 0,
        };
      }

      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = getNumericScore(evaluations[withKey]);
      const withoutEval = getNumericScore(evaluations[withoutKey]);

      if (withEval !== null) {
        embeddingStats[result.embedding_provider].withContext.push(withEval);
        embeddingStats[result.embedding_provider].totalEvaluated++;
      }
      if (withoutEval !== null) {
        embeddingStats[result.embedding_provider].withoutContext.push(
          withoutEval
        );
        embeddingStats[result.embedding_provider].totalEvaluated++;
      }
    });

    return embeddingStats;
  }

  // Calculate average
  function average(numbers: number[]): number {
    return numbers.length > 0
      ? numbers.reduce((a, b) => a + b, 0) / numbers.length
      : 0;
  }

  // Get color for performance score
  function getPerformanceColor(score: number): string {
    if (score >= 2.5) return "#28a745"; // Green
    if (score >= 2.0) return "#20c997"; // Teal
    if (score >= 1.5) return "#ffc107"; // Yellow
    if (score >= 1.0) return "#fd7e14"; // Orange
    return "#dc3545"; // Red
  }

  // Get color for context impact
  function getImpactColor(impact: number): string {
    if (impact > 0.5) return "#28a745"; // Green (positive)
    if (impact > 0) return "#20c997"; // Light green
    if (impact === 0) return "#6c757d"; // Gray (neutral)
    if (impact > -0.5) return "#ffc107"; // Yellow (slight negative)
    return "#dc3545"; // Red (very negative)
  }

  // Reactive calculations
  let modelMetrics = $derived(calculateModelMetrics());
  let embeddingMetrics = $derived(calculateEmbeddingMetrics());
</script>

<div class="dashboard">
  <h2>📈 Analytics Dashboard</h2>

  <!-- Summary Stats -->
  <div class="summary-section">
    <h3>📊 Overview</h3>
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-number">{data.length}</div>
        <div class="summary-label">Total Comparisons</div>
      </div>
      <div class="summary-card">
        <div class="summary-number">{Object.keys(modelMetrics).length}</div>
        <div class="summary-label">Models Tested</div>
      </div>
      <div class="summary-card">
        <div class="summary-number">{Object.keys(embeddingMetrics).length}</div>
        <div class="summary-label">Embedding Providers</div>
      </div>
      <div class="summary-card">
        <div class="summary-number">
          {Object.values(modelMetrics).reduce(
            (sum, m) => sum + m.totalEvaluated,
            0
          )}
        </div>
        <div class="summary-label">Total Evaluations</div>
      </div>
    </div>
  </div>

  <!-- Model Comparison -->
  <div class="comparison-section">
    <h3>🤖 Model Performance Comparison</h3>
    <div class="chart-container">
      {#each Object.entries(modelMetrics) as [modelName, stats]}
        <div class="model-row">
          <div class="model-name">{modelName}</div>
          <div class="performance-bars">
            <div class="performance-item">
              <span class="performance-label">With Context:</span>
              <div class="progress-bar-chart">
                <div
                  class="progress-fill-chart"
                  style="width: {(average(stats.withContext) / 3) *
                    100}%; background-color: {getPerformanceColor(
                    average(stats.withContext)
                  )}"
                ></div>
              </div>
              <span class="performance-score"
                >{average(stats.withContext).toFixed(2)}</span
              >
            </div>
            <div class="performance-item">
              <span class="performance-label">Without Context:</span>
              <div class="progress-bar-chart">
                <div
                  class="progress-fill-chart"
                  style="width: {(average(stats.withoutContext) / 3) *
                    100}%; background-color: {getPerformanceColor(
                    average(stats.withoutContext)
                  )}"
                ></div>
              </div>
              <span class="performance-score"
                >{average(stats.withoutContext).toFixed(2)}</span
              >
            </div>
            <div class="performance-item">
              <span class="performance-label">Context Impact:</span>
              <div
                class="impact-indicator"
                style="background-color: {getImpactColor(
                  average(stats.contextImpact)
                )}"
              >
                {average(stats.contextImpact) > 0 ? "+" : ""}{average(
                  stats.contextImpact
                ).toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Embedding Provider Comparison -->
  <div class="comparison-section">
    <h3>🔗 Embedding Provider Comparison</h3>
    <div class="chart-container">
      {#each Object.entries(embeddingMetrics) as [providerName, stats]}
        <div class="model-row">
          <div class="model-name">{providerName}</div>
          <div class="performance-bars">
            <div class="performance-item">
              <span class="performance-label">With Context:</span>
              <div class="progress-bar-chart">
                <div
                  class="progress-fill-chart"
                  style="width: {(average(stats.withContext) / 3) *
                    100}%; background-color: {getPerformanceColor(
                    average(stats.withContext)
                  )}"
                ></div>
              </div>
              <span class="performance-score"
                >{average(stats.withContext).toFixed(2)}</span
              >
            </div>
            <div class="performance-item">
              <span class="performance-label">Without Context:</span>
              <div class="progress-bar-chart">
                <div
                  class="progress-fill-chart"
                  style="width: {(average(stats.withoutContext) / 3) *
                    100}%; background-color: {getPerformanceColor(
                    average(stats.withoutContext)
                  )}"
                ></div>
              </div>
              <span class="performance-score"
                >{average(stats.withoutContext).toFixed(2)}</span
              >
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Context Impact Analysis -->
  <div class="comparison-section">
    <h3>⚖️ Context vs No Context Analysis</h3>
    <div class="context-analysis">
      <div class="analysis-grid">
        <div class="analysis-card positive">
          <div class="analysis-number">
            {Object.values(modelMetrics).reduce(
              (sum, m) =>
                sum + m.contextImpact.filter((impact) => impact > 0).length,
              0
            )}
          </div>
          <div class="analysis-label">Positive Impact Cases</div>
        </div>
        <div class="analysis-card neutral">
          <div class="analysis-number">
            {Object.values(modelMetrics).reduce(
              (sum, m) =>
                sum + m.contextImpact.filter((impact) => impact === 0).length,
              0
            )}
          </div>
          <div class="analysis-label">No Change Cases</div>
        </div>
        <div class="analysis-card negative">
          <div class="analysis-number">
            {Object.values(modelMetrics).reduce(
              (sum, m) =>
                sum + m.contextImpact.filter((impact) => impact < 0).length,
              0
            )}
          </div>
          <div class="analysis-label">Negative Impact Cases</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Model-with-Context Ranking -->
  <div class="comparison-section">
    <h3>🏆 Model Ranking (With Context Only)</h3>
    <div class="ranking-table">
      {#each Object.entries(modelMetrics)
        .filter(([_, stats]) => stats.withContext.length > 0)
        .sort(([_a, a], [_b, b]) => average(b.withContext) - average(a.withContext)) as [modelName, stats], index}
        <div class="ranking-row">
          <div class="rank-position">#{index + 1}</div>
          <div class="rank-model">{modelName}</div>
          <div class="rank-score">
            <div class="score-bar">
              <div
                class="score-fill"
                style="width: {(average(stats.withContext) / 3) *
                  100}%; background-color: {getPerformanceColor(
                  average(stats.withContext)
                )}"
              ></div>
            </div>
            <span class="score-text"
              >{average(stats.withContext).toFixed(2)}/3.00</span
            >
          </div>
          <div class="rank-count">{stats.withContext.length} evaluations</div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .dashboard {
    background: white;
    border-radius: 8px;
    padding: 2rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .dashboard h2 {
    margin-top: 0;
    margin-bottom: 2rem;
    color: #333;
    font-size: 1.8rem;
    text-align: center;
  }

  .dashboard h3 {
    color: #333;
    margin-bottom: 1rem;
    font-size: 1.3rem;
    border-bottom: 2px solid #e9ecef;
    padding-bottom: 0.5rem;
  }

  .summary-section {
    margin-bottom: 2rem;
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .summary-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
  }

  .summary-number {
    font-size: 2rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
  }

  .summary-label {
    font-size: 0.9rem;
    opacity: 0.9;
  }

  .comparison-section {
    margin-bottom: 2rem;
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid #e9ecef;
  }

  .chart-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .model-row {
    display: flex;
    align-items: center;
    background: white;
    padding: 1rem;
    border-radius: 6px;
    border: 1px solid #dee2e6;
  }

  .model-name {
    min-width: 150px;
    font-weight: 600;
    color: #333;
  }

  .performance-bars {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-left: 1rem;
  }

  .performance-item {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .performance-label {
    min-width: 120px;
    font-size: 0.9rem;
    color: #666;
  }

  .progress-bar-chart {
    flex: 1;
    height: 20px;
    background-color: #e9ecef;
    border-radius: 10px;
    overflow: hidden;
    max-width: 200px;
  }

  .progress-fill-chart {
    height: 100%;
    border-radius: 10px;
    transition: width 0.3s ease;
  }

  .performance-score {
    min-width: 40px;
    font-weight: 600;
    color: #333;
  }

  .impact-indicator {
    padding: 0.25rem 0.75rem;
    border-radius: 15px;
    color: white;
    font-weight: 600;
    font-size: 0.9rem;
    min-width: 60px;
    text-align: center;
  }

  .context-analysis {
    margin-top: 1rem;
  }

  .analysis-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }

  .analysis-card {
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
    color: white;
  }

  .analysis-card.positive {
    background: linear-gradient(135deg, #28a745, #20c997);
  }

  .analysis-card.neutral {
    background: linear-gradient(135deg, #6c757d, #495057);
  }

  .analysis-card.negative {
    background: linear-gradient(135deg, #dc3545, #c82333);
  }

  .analysis-number {
    font-size: 1.8rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
  }

  .analysis-label {
    font-size: 0.9rem;
    opacity: 0.9;
  }

  .ranking-table {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .ranking-row {
    display: flex;
    align-items: center;
    background: white;
    padding: 1rem;
    border-radius: 6px;
    border: 1px solid #dee2e6;
    gap: 1rem;
  }

  .rank-position {
    font-size: 1.2rem;
    font-weight: bold;
    color: #007bff;
    min-width: 40px;
  }

  .rank-model {
    flex: 1;
    font-weight: 600;
    color: #333;
  }

  .rank-score {
    display: flex;
    align-items: center;
    gap: 1rem;
    min-width: 200px;
  }

  .score-bar {
    flex: 1;
    height: 16px;
    background-color: #e9ecef;
    border-radius: 8px;
    overflow: hidden;
  }

  .score-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.3s ease;
  }

  .score-text {
    font-weight: 600;
    color: #333;
    min-width: 70px;
  }

  .rank-count {
    font-size: 0.9rem;
    color: #666;
    min-width: 100px;
  }

  @media (max-width: 768px) {
    .dashboard {
      padding: 1.5rem;
    }

    .dashboard h2 {
      font-size: 1.5rem;
    }

    .summary-grid {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }

    .model-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }

    .performance-bars {
      margin-left: 0;
      width: 100%;
    }

    .performance-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .progress-bar-chart {
      max-width: 100%;
    }

    .ranking-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
    }

    .rank-score {
      width: 100%;
      min-width: unset;
    }
  }
</style>
