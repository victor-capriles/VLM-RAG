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

  // Count words in a string
  function countWords(text: string): number {
    return text
      .trim()
      .split(/\s+/)
      .filter((word) => word.length > 0).length;
  }

  // Get conciseness level info
  function getConcisenessPenalty(response: string): number {
    const wordCount = countWords(response);

    if (wordCount < 10) return 0.1; // Brief
    if (wordCount <= 50) return 0.0; // Ideal
    if (wordCount <= 100) return 0.2; // Verbose
    if (wordCount <= 150) return 0.4; // Long
    return 0.6; // Excessive
  }

  // Get conciseness level name and color
  function getConcisenesslevel(response: string): {
    level: string;
    color: string;
    penalty: number;
  } {
    const wordCount = countWords(response);
    const penalty = getConcisenessPenalty(response);

    if (wordCount < 10) return { level: "Brief", color: "#ffc107", penalty };
    if (wordCount <= 50) return { level: "Ideal", color: "#28a745", penalty };
    if (wordCount <= 100)
      return { level: "Verbose", color: "#fd7e14", penalty };
    if (wordCount <= 150) return { level: "Long", color: "#dc3545", penalty };
    return { level: "Excessive", color: "#6f42c1", penalty };
  }

  // Calculate text length metrics by model
  function calculateTextLengthMetrics() {
    const lengthStats: Record<
      string,
      {
        withContext: { words: number[]; levels: string[] };
        withoutContext: { words: number[]; levels: string[] };
      }
    > = {};

    data.forEach((result) => {
      if (!lengthStats[result.model_name]) {
        lengthStats[result.model_name] = {
          withContext: { words: [], levels: [] },
          withoutContext: { words: [], levels: [] },
        };
      }

      if (result.with_context) {
        const wordCount = countWords(result.with_context.llm_response);
        const level = getConcisenesslevel(result.with_context.llm_response);
        lengthStats[result.model_name].withContext.words.push(wordCount);
        lengthStats[result.model_name].withContext.levels.push(level.level);
      }

      if (result.without_context) {
        const wordCount = countWords(result.without_context.llm_response);
        const level = getConcisenesslevel(result.without_context.llm_response);
        lengthStats[result.model_name].withoutContext.words.push(wordCount);
        lengthStats[result.model_name].withoutContext.levels.push(level.level);
      }
    });

    return lengthStats;
  }

  // Calculate text length metrics by embedding provider
  function calculateEmbeddingLengthMetrics() {
    const lengthStats: Record<
      string,
      {
        withContext: { words: number[]; levels: string[] };
        withoutContext: { words: number[]; levels: string[] };
      }
    > = {};

    data.forEach((result) => {
      if (!lengthStats[result.embedding_provider]) {
        lengthStats[result.embedding_provider] = {
          withContext: { words: [], levels: [] },
          withoutContext: { words: [], levels: [] },
        };
      }

      if (result.with_context) {
        const wordCount = countWords(result.with_context.llm_response);
        const level = getConcisenesslevel(result.with_context.llm_response);
        lengthStats[result.embedding_provider].withContext.words.push(
          wordCount
        );
        lengthStats[result.embedding_provider].withContext.levels.push(
          level.level
        );
      }

      if (result.without_context) {
        const wordCount = countWords(result.without_context.llm_response);
        const level = getConcisenesslevel(result.without_context.llm_response);
        lengthStats[result.embedding_provider].withoutContext.words.push(
          wordCount
        );
        lengthStats[result.embedding_provider].withoutContext.levels.push(
          level.level
        );
      }
    });

    return lengthStats;
  }

  // Calculate overall text length statistics
  function calculateOverallLengthStats() {
    const allWithContext: number[] = [];
    const allWithoutContext: number[] = [];
    const levelDistribution: Record<string, { with: number; without: number }> =
      {
        Brief: { with: 0, without: 0 },
        Ideal: { with: 0, without: 0 },
        Verbose: { with: 0, without: 0 },
        Long: { with: 0, without: 0 },
        Excessive: { with: 0, without: 0 },
      };

    data.forEach((result) => {
      if (result.with_context) {
        const wordCount = countWords(result.with_context.llm_response);
        const level = getConcisenesslevel(result.with_context.llm_response);
        allWithContext.push(wordCount);
        levelDistribution[level.level].with++;
      }

      if (result.without_context) {
        const wordCount = countWords(result.without_context.llm_response);
        const level = getConcisenesslevel(result.without_context.llm_response);
        allWithoutContext.push(wordCount);
        levelDistribution[level.level].without++;
      }
    });

    return {
      withContext: {
        avg: average(allWithContext),
        min: allWithContext.length > 0 ? Math.min(...allWithContext) : 0,
        max: allWithContext.length > 0 ? Math.max(...allWithContext) : 0,
        count: allWithContext.length,
      },
      withoutContext: {
        avg: average(allWithoutContext),
        min: allWithoutContext.length > 0 ? Math.min(...allWithoutContext) : 0,
        max: allWithoutContext.length > 0 ? Math.max(...allWithoutContext) : 0,
        count: allWithoutContext.length,
      },
      levelDistribution,
    };
  }

  // Get category name and info from numeric score
  function getCategoryInfo(score: number): {
    name: string;
    emoji: string;
    color: string;
  } {
    switch (score) {
      case 3:
        return { name: "Direct", emoji: "✅", color: "#28a745" };
      case 2:
        return { name: "Inferable", emoji: "💡", color: "#17a2b8" };
      case 1:
        return { name: "Missing", emoji: "❌", color: "#ffc107" };
      case 0:
        return { name: "Hallucination", emoji: "🤯", color: "#dc3545" };
      default:
        return { name: "Unknown", emoji: "❓", color: "#6c757d" };
    }
  }

  // Calculate category distribution by model
  function calculateCategoryMetricsByModel() {
    const evaluations = getEvaluations();
    const modelStats: Record<
      string,
      {
        categories: Record<number, number>;
        total: number;
        withContext: Record<number, number>;
        withoutContext: Record<number, number>;
      }
    > = {};

    data.forEach((result) => {
      if (!modelStats[result.model_name]) {
        modelStats[result.model_name] = {
          categories: { 0: 0, 1: 0, 2: 0, 3: 0 },
          total: 0,
          withContext: { 0: 0, 1: 0, 2: 0, 3: 0 },
          withoutContext: { 0: 0, 1: 0, 2: 0, 3: 0 },
        };
      }

      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = getNumericScore(evaluations[withKey]);
      const withoutEval = getNumericScore(evaluations[withoutKey]);

      if (withEval !== null && withEval >= 0) {
        const categoryIndex = 3 - withEval; // Convert score to category index
        modelStats[result.model_name].categories[categoryIndex]++;
        modelStats[result.model_name].withContext[categoryIndex]++;
        modelStats[result.model_name].total++;
      }

      if (withoutEval !== null && withoutEval >= 0) {
        const categoryIndex = 3 - withoutEval; // Convert score to category index
        modelStats[result.model_name].categories[categoryIndex]++;
        modelStats[result.model_name].withoutContext[categoryIndex]++;
        modelStats[result.model_name].total++;
      }
    });

    return modelStats;
  }

  // Calculate category distribution by embedding provider
  function calculateCategoryMetricsByEmbedding() {
    const evaluations = getEvaluations();
    const embeddingStats: Record<
      string,
      {
        categories: Record<number, number>;
        total: number;
        withContext: Record<number, number>;
        withoutContext: Record<number, number>;
      }
    > = {};

    data.forEach((result) => {
      if (!embeddingStats[result.embedding_provider]) {
        embeddingStats[result.embedding_provider] = {
          categories: { 0: 0, 1: 0, 2: 0, 3: 0 },
          total: 0,
          withContext: { 0: 0, 1: 0, 2: 0, 3: 0 },
          withoutContext: { 0: 0, 1: 0, 2: 0, 3: 0 },
        };
      }

      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = getNumericScore(evaluations[withKey]);
      const withoutEval = getNumericScore(evaluations[withoutKey]);

      if (withEval !== null && withEval >= 0) {
        const categoryIndex = 3 - withEval; // Convert score to category index
        embeddingStats[result.embedding_provider].categories[categoryIndex]++;
        embeddingStats[result.embedding_provider].withContext[categoryIndex]++;
        embeddingStats[result.embedding_provider].total++;
      }

      if (withoutEval !== null && withoutEval >= 0) {
        const categoryIndex = 3 - withoutEval; // Convert score to category index
        embeddingStats[result.embedding_provider].categories[categoryIndex]++;
        embeddingStats[result.embedding_provider].withoutContext[
          categoryIndex
        ]++;
        embeddingStats[result.embedding_provider].total++;
      }
    });

    return embeddingStats;
  }

  // Get top performers for specific categories
  function getTopPerformers() {
    const modelCategories = calculateCategoryMetricsByModel();
    const embeddingCategories = calculateCategoryMetricsByEmbedding();

    // Find model with most Direct responses (category 0)
    const topModelDirect = Object.entries(modelCategories).sort(
      ([, a], [, b]) => b.categories[0] - a.categories[0]
    )[0];

    // Find embedding with most Direct responses (category 0)
    const topEmbeddingDirect = Object.entries(embeddingCategories).sort(
      ([, a], [, b]) => b.categories[0] - a.categories[0]
    )[0];

    // Find model with most Hallucinations (category 3)
    const topModelHallucination = Object.entries(modelCategories).sort(
      ([, a], [, b]) => b.categories[3] - a.categories[3]
    )[0];

    // Find embedding with most Hallucinations (category 3)
    const topEmbeddingHallucination = Object.entries(embeddingCategories).sort(
      ([, a], [, b]) => b.categories[3] - a.categories[3]
    )[0];

    return {
      modelDirect: topModelDirect,
      embeddingDirect: topEmbeddingDirect,
      modelHallucination: topModelHallucination,
      embeddingHallucination: topEmbeddingHallucination,
    };
  }

  // Reactive calculations
  let modelMetrics = $derived(calculateModelMetrics());
  let embeddingMetrics = $derived(calculateEmbeddingMetrics());
  let textLengthMetrics = $derived(calculateTextLengthMetrics());
  let embeddingLengthMetrics = $derived(calculateEmbeddingLengthMetrics());
  let overallLengthStats = $derived(calculateOverallLengthStats());
  let categoryMetricsByModel = $derived(calculateCategoryMetricsByModel());
  let categoryMetricsByEmbedding = $derived(
    calculateCategoryMetricsByEmbedding()
  );
  let topPerformers = $derived(getTopPerformers());
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

  <!-- Text Length Overview -->
  <div class="comparison-section">
    <h3>📝 Text Length Overview</h3>
    <div class="length-overview">
      <div class="overview-stats">
        <div class="stat-card">
          <div class="stat-title">With Context</div>
          <div class="stat-value">
            {overallLengthStats.withContext.avg.toFixed(1)}
          </div>
          <div class="stat-label">Avg Words</div>
          <div class="stat-range">
            {overallLengthStats.withContext.min} - {overallLengthStats
              .withContext.max} words
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-title">Without Context</div>
          <div class="stat-value">
            {overallLengthStats.withoutContext.avg.toFixed(1)}
          </div>
          <div class="stat-label">Avg Words</div>
          <div class="stat-range">
            {overallLengthStats.withoutContext.min} - {overallLengthStats
              .withoutContext.max} words
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-title">Context Impact</div>
          <div
            class="stat-value {overallLengthStats.withContext.avg -
              overallLengthStats.withoutContext.avg >
            0
              ? 'positive'
              : 'negative'}"
          >
            {(
              overallLengthStats.withContext.avg -
              overallLengthStats.withoutContext.avg
            ).toFixed(1)}
          </div>
          <div class="stat-label">Word Difference</div>
          <div class="stat-range">
            {overallLengthStats.withContext.avg >
            overallLengthStats.withoutContext.avg
              ? "More"
              : "Less"} verbose with context
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Conciseness Level Distribution -->
  <div class="comparison-section">
    <h3>🎯 Conciseness Level Distribution</h3>
    <div class="conciseness-grid">
      {#each Object.entries(overallLengthStats.levelDistribution) as [level, counts]}
        <div class="conciseness-card">
          <div class="conciseness-header">
            <div
              class="conciseness-level-badge"
              style="background-color: {getConcisenesslevel(
                'x'.repeat(
                  level === 'Brief'
                    ? 5
                    : level === 'Ideal'
                      ? 25
                      : level === 'Verbose'
                        ? 75
                        : level === 'Long'
                          ? 125
                          : 175
                )
              ).color}"
            >
              {level}
            </div>
          </div>
          <div class="conciseness-counts">
            <div class="count-row">
              <span class="count-label">With Context:</span>
              <span class="count-value">{counts.with}</span>
            </div>
            <div class="count-row">
              <span class="count-label">Without Context:</span>
              <span class="count-value">{counts.without}</span>
            </div>
            <div class="count-total">
              Total: {counts.with + counts.without}
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Model Text Length Comparison -->
  <div class="comparison-section">
    <h3>🤖 Model Text Length Comparison</h3>
    <div class="chart-container">
      {#each Object.entries(textLengthMetrics) as [modelName, stats]}
        <div class="model-row">
          <div class="model-name">{modelName}</div>
          <div class="length-bars">
            <div class="length-item">
              <span class="length-label">With Context:</span>
              <div class="length-value">
                {average(stats.withContext.words).toFixed(1)} words
              </div>
              <div class="length-bar">
                <div
                  class="length-fill"
                  style="width: {Math.min(
                    (average(stats.withContext.words) / 200) * 100,
                    100
                  )}%; background-color: {getConcisenesslevel(
                    'x'.repeat(Math.floor(average(stats.withContext.words)))
                  ).color}"
                ></div>
              </div>
            </div>
            <div class="length-item">
              <span class="length-label">Without Context:</span>
              <div class="length-value">
                {average(stats.withoutContext.words).toFixed(1)} words
              </div>
              <div class="length-bar">
                <div
                  class="length-fill"
                  style="width: {Math.min(
                    (average(stats.withoutContext.words) / 200) * 100,
                    100
                  )}%; background-color: {getConcisenesslevel(
                    'x'.repeat(Math.floor(average(stats.withoutContext.words)))
                  ).color}"
                ></div>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Embedding Provider Text Length Comparison -->
  <div class="comparison-section">
    <h3>🔗 Embedding Provider Text Length Comparison</h3>
    <div class="chart-container">
      {#each Object.entries(embeddingLengthMetrics) as [providerName, stats]}
        <div class="model-row">
          <div class="model-name">{providerName}</div>
          <div class="length-bars">
            <div class="length-item">
              <span class="length-label">With Context:</span>
              <div class="length-value">
                {average(stats.withContext.words).toFixed(1)} words
              </div>
              <div class="length-bar">
                <div
                  class="length-fill"
                  style="width: {Math.min(
                    (average(stats.withContext.words) / 200) * 100,
                    100
                  )}%; background-color: {getConcisenesslevel(
                    'x'.repeat(Math.floor(average(stats.withContext.words)))
                  ).color}"
                ></div>
              </div>
            </div>
            <div class="length-item">
              <span class="length-label">Without Context:</span>
              <div class="length-value">
                {average(stats.withoutContext.words).toFixed(1)} words
              </div>
              <div class="length-bar">
                <div
                  class="length-fill"
                  style="width: {Math.min(
                    (average(stats.withoutContext.words) / 200) * 100,
                    100
                  )}%; background-color: {getConcisenesslevel(
                    'x'.repeat(Math.floor(average(stats.withoutContext.words)))
                  ).color}"
                ></div>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Category Analysis Top Performers -->
  <div class="comparison-section">
    <h3>🏅 Category Analysis - Top Performers</h3>
    <div class="top-performers-grid">
      <div class="performer-card best">
        <div class="performer-header">
          <div class="performer-emoji">🎯</div>
          <div class="performer-title">Most Direct Responses</div>
        </div>
        <div class="performer-content">
          <div class="performer-model">
            <strong>Model:</strong>
            {topPerformers.modelDirect?.[0] || "N/A"}
            <span class="performer-count"
              >({topPerformers.modelDirect?.[1]?.categories[0] || 0} Direct)</span
            >
          </div>
          <div class="performer-embedding">
            <strong>Embedding:</strong>
            {topPerformers.embeddingDirect?.[0] || "N/A"}
            <span class="performer-count"
              >({topPerformers.embeddingDirect?.[1]?.categories[0] || 0} Direct)</span
            >
          </div>
        </div>
      </div>

      <div class="performer-card worst">
        <div class="performer-header">
          <div class="performer-emoji">🚨</div>
          <div class="performer-title">Most Hallucinations</div>
        </div>
        <div class="performer-content">
          <div class="performer-model">
            <strong>Model:</strong>
            {topPerformers.modelHallucination?.[0] || "N/A"}
            <span class="performer-count"
              >({topPerformers.modelHallucination?.[1]?.categories[3] || 0} Hallucinations)</span
            >
          </div>
          <div class="performer-embedding">
            <strong>Embedding:</strong>
            {topPerformers.embeddingHallucination?.[0] || "N/A"}
            <span class="performer-count"
              >({topPerformers.embeddingHallucination?.[1]?.categories[3] || 0} Hallucinations)</span
            >
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Model Category Distribution -->
  <div class="comparison-section">
    <h3>🤖 Model Category Distribution</h3>
    <div class="category-charts">
      {#each Object.entries(categoryMetricsByModel) as [modelName, stats]}
        <div class="category-chart">
          <div class="chart-header">
            <div class="chart-title">{modelName}</div>
            <div class="chart-total">Total: {stats.total} evaluations</div>
          </div>
          <div class="category-bars">
            {#each [0, 1, 2, 3] as categoryIndex}
              {@const score = 3 - categoryIndex}
              {@const categoryInfo = getCategoryInfo(score)}
              {@const count = stats.categories[categoryIndex]}
              {@const percentage =
                stats.total > 0 ? (count / stats.total) * 100 : 0}
              <div class="category-bar">
                <div class="category-label">
                  <span class="category-emoji">{categoryInfo.emoji}</span>
                  <span class="category-name">{categoryInfo.name}</span>
                </div>
                <div class="bar-container">
                  <div
                    class="bar-fill"
                    style="width: {percentage}%; background-color: {categoryInfo.color}"
                  ></div>
                  <span class="bar-text"
                    >{count} ({percentage.toFixed(1)}%)</span
                  >
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Embedding Category Distribution -->
  <div class="comparison-section">
    <h3>🔗 Embedding Provider Category Distribution</h3>
    <div class="category-charts">
      {#each Object.entries(categoryMetricsByEmbedding) as [embeddingName, stats]}
        <div class="category-chart">
          <div class="chart-header">
            <div class="chart-title">{embeddingName}</div>
            <div class="chart-total">Total: {stats.total} evaluations</div>
          </div>
          <div class="category-bars">
            {#each [0, 1, 2, 3] as categoryIndex}
              {@const score = 3 - categoryIndex}
              {@const categoryInfo = getCategoryInfo(score)}
              {@const count = stats.categories[categoryIndex]}
              {@const percentage =
                stats.total > 0 ? (count / stats.total) * 100 : 0}
              <div class="category-bar">
                <div class="category-label">
                  <span class="category-emoji">{categoryInfo.emoji}</span>
                  <span class="category-name">{categoryInfo.name}</span>
                </div>
                <div class="bar-container">
                  <div
                    class="bar-fill"
                    style="width: {percentage}%; background-color: {categoryInfo.color}"
                  ></div>
                  <span class="bar-text"
                    >{count} ({percentage.toFixed(1)}%)</span
                  >
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
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

  /* Text Length Metrics Styles */
  .length-overview {
    margin-top: 1rem;
  }

  .overview-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
  }

  .stat-card {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid #dee2e6;
    text-align: center;
  }

  .stat-title {
    font-size: 0.9rem;
    color: #666;
    margin-bottom: 0.5rem;
  }

  .stat-value {
    font-size: 2rem;
    font-weight: bold;
    color: #333;
    margin-bottom: 0.5rem;
  }

  .stat-value.positive {
    color: #28a745;
  }

  .stat-value.negative {
    color: #dc3545;
  }

  .stat-label {
    font-size: 0.9rem;
    color: #333;
    margin-bottom: 0.5rem;
  }

  .stat-range {
    font-size: 0.8rem;
    color: #666;
  }

  .conciseness-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }

  .conciseness-card {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    border: 1px solid #dee2e6;
  }

  .conciseness-header {
    margin-bottom: 1rem;
    text-align: center;
  }

  .conciseness-level-badge {
    padding: 0.5rem 1rem;
    border-radius: 20px;
    color: white;
    font-weight: bold;
    font-size: 0.9rem;
    display: inline-block;
  }

  .conciseness-counts {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .count-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .count-label {
    font-size: 0.9rem;
    color: #666;
  }

  .count-value {
    font-weight: bold;
    color: #333;
  }

  .count-total {
    font-weight: bold;
    color: #007bff;
    text-align: center;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid #e9ecef;
  }

  .length-bars {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-left: 1rem;
  }

  .length-item {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .length-label {
    min-width: 120px;
    font-size: 0.9rem;
    color: #666;
  }

  .length-value {
    min-width: 80px;
    font-weight: 600;
    color: #333;
    font-size: 0.9rem;
  }

  .length-bar {
    flex: 1;
    height: 16px;
    background-color: #e9ecef;
    border-radius: 8px;
    overflow: hidden;
    max-width: 200px;
  }

  .length-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.3s ease;
  }

  /* Category Analysis Styles */
  .top-performers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }

  .performer-card {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    border: 2px solid;
  }

  .performer-card.best {
    border-color: #28a745;
    background: linear-gradient(135deg, #f8fff9 0%, #e8f5e8 100%);
  }

  .performer-card.worst {
    border-color: #dc3545;
    background: linear-gradient(135deg, #fff8f8 0%, #f5e8e8 100%);
  }

  .performer-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .performer-emoji {
    font-size: 2rem;
  }

  .performer-title {
    font-size: 1.2rem;
    font-weight: bold;
    color: #333;
  }

  .performer-content {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .performer-model,
  .performer-embedding {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .performer-count {
    color: #666;
    font-size: 0.9rem;
  }

  .category-charts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }

  .category-chart {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid #dee2e6;
  }

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e9ecef;
  }

  .chart-title {
    font-weight: bold;
    color: #333;
    font-size: 1.1rem;
  }

  .chart-total {
    color: #666;
    font-size: 0.9rem;
  }

  .category-bars {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .category-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .category-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 120px;
  }

  .category-emoji {
    font-size: 1.2rem;
  }

  .category-name {
    font-weight: 500;
    color: #333;
  }

  .bar-container {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .bar-fill {
    height: 20px;
    border-radius: 10px;
    min-width: 2px;
    transition: width 0.3s ease;
  }

  .bar-text {
    min-width: 80px;
    font-size: 0.9rem;
    color: #333;
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .overview-stats {
      grid-template-columns: 1fr;
    }

    .conciseness-grid {
      grid-template-columns: 1fr;
    }

    .length-bars {
      margin-left: 0;
    }

    .length-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .length-bar {
      max-width: 100%;
      width: 100%;
    }

    .top-performers-grid {
      grid-template-columns: 1fr;
    }

    .category-charts {
      grid-template-columns: 1fr;
    }

    .category-bar {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .bar-container {
      width: 100%;
    }
  }
</style>
