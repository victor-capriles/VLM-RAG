<script lang="ts">
  import ResultsTable from "$lib/components/ResultsTable.svelte";
  import Dashboard from "$lib/components/Dashboard.svelte";
  import { onMount } from "svelte";

  // Type definitions
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

  // State variables
  let rawResults: RawResult[] = $state([]);
  let selectedModel = $state("all");
  let selectedContext = $state("all");
  let selectedEmbedding = $state("all");
  let selectedContextImpact = $state("all");
  // UI state
  let showFilters = $state(false);
  let activeTab = $state("results"); // "results" or "dashboard"

  // Infinite scroll state
  let visibleItemsLimit = $state(50); // Start with 50 items
  let isLoadingMore = $state(false);
  const ITEMS_PER_LOAD = 25; // Load 25 more items each time
  let scrollSentinel: HTMLElement | undefined; // Element to observe for intersection

  // Force reactivity when evaluations change
  let evaluationUpdateTrigger = $state(0);

  // Set up intersection observer for infinite scroll
  let observer: IntersectionObserver | undefined;

  onMount(() => {
    if (typeof window === "undefined") return;

    observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting && !isLoadingMore) {
          loadMoreItems();
        }
      },
      {
        rootMargin: "100px", // Trigger 100px before the sentinel becomes visible
      }
    );

    // Cleanup
    return () => {
      if (observer) {
        observer.disconnect();
      }
    };
  });

  // Watch for when the sentinel element becomes available
  $effect(() => {
    if (observer && scrollSentinel) {
      observer.observe(scrollSentinel);

      // Return cleanup function
      return () => {
        if (observer && scrollSentinel) {
          observer.unobserve(scrollSentinel);
        }
      };
    }
  });

  // Reset visible items when filters change
  $effect(() => {
    // Watch filter changes
    selectedModel;
    selectedContext;
    selectedEmbedding;
    selectedContextImpact;

    // Reset to initial limit when filters change
    visibleItemsLimit = 50;
  });

  // Data Loading
  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (!text) return;

      try {
        // Try to parse as JSON first (exported data with evaluations)
        let parsedData;
        try {
          parsedData = JSON.parse(text);
        } catch {
          // If JSON parsing fails, treat as JSONL
          parsedData = null;
        }

        if (parsedData && parsedData.data && parsedData.version) {
          // This is an exported file with evaluations
          console.log("Loading exported data with evaluations...");
          rawResults = parsedData.data;

          // Extract evaluations from the integrated data format
          const evaluations: Record<string, string> = {};

          // Convert numbers back to evaluation strings
          const numberToEvaluation = (num: number | null): string | null => {
            switch (num) {
              case 3:
                return "directly_answered";
              case 2:
                return "inferable";
              case 1:
                return "missing_incorrect";
              case 0:
                return "hallucination";
              default:
                return null;
            }
          };

          for (const result of parsedData.data) {
            const key = `${result.validation_id}-${result.model_name}-${result.embedding_provider}`;

            // Extract with_context evaluation
            if (result.evaluation_with_context !== undefined) {
              const withKey = `${key}-with`;
              const evaluation = numberToEvaluation(
                result.evaluation_with_context
              );
              if (evaluation) {
                evaluations[withKey] = evaluation;
              }
            }

            // Extract without_context evaluation
            if (result.evaluation_without_context !== undefined) {
              const withoutKey = `${key}-without`;
              const evaluation = numberToEvaluation(
                result.evaluation_without_context
              );
              if (evaluation) {
                evaluations[withoutKey] = evaluation;
              }
            }
          }

          // Restore evaluations to sessionStorage (also handle legacy format)
          if (Object.keys(evaluations).length > 0) {
            if (typeof window !== "undefined") {
              sessionStorage.setItem(
                "llm-evaluations",
                JSON.stringify(evaluations)
              );
              console.log(
                "Restored",
                Object.keys(evaluations).length,
                "evaluations from integrated format"
              );
              // Notify all ResultRow components that evaluations were loaded
              window.dispatchEvent(new CustomEvent("evaluationsCleared")); // Use same event to force refresh
            }
          } else if (parsedData.evaluations) {
            // Legacy format support
            if (typeof window !== "undefined") {
              sessionStorage.setItem(
                "llm-evaluations",
                JSON.stringify(parsedData.evaluations)
              );
              console.log(
                "Restored",
                Object.keys(parsedData.evaluations).length,
                "evaluations from legacy format"
              );
              // Notify all ResultRow components that evaluations were loaded
              window.dispatchEvent(new CustomEvent("evaluationsCleared")); // Use same event to force refresh
            }
          }

          // Force progress update
          forceProgressUpdate();

          alert(
            `Loaded ${rawResults.length} results with ${Object.keys(evaluations).length || Object.keys(parsedData.evaluations || {}).length} evaluations!`
          );
        } else {
          // Regular JSONL file
          const lines = text.trim().split("\n");
          const parsed: RawResult[] = [];

          for (const line of lines) {
            if (line.trim()) {
              parsed.push(JSON.parse(line));
            }
          }

          rawResults = parsed;
          console.log("Loaded JSONL data:", parsed.length, "results");
          forceProgressUpdate(); // Update progress bar
        }
      } catch (error) {
        alert("Error parsing file: " + error);
      }
    };

    reader.readAsText(file);
  }

  // Export evaluations with original data
  function exportEvaluations() {
    if (rawResults.length === 0) {
      alert("No data to export. Please load a file first.");
      return;
    }

    // Get current evaluations from sessionStorage
    const evaluationsJson =
      typeof window !== "undefined"
        ? sessionStorage.getItem("llm-evaluations")
        : null;
    const evaluations = evaluationsJson ? JSON.parse(evaluationsJson) : {};

    // Convert evaluation strings to numbers
    const evaluationToNumber = (evaluation: string | null): number | null => {
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
    };

    // Add evaluations to each result
    const dataWithEvaluations = rawResults.map((result) => {
      const key = `${result.validation_id}-${result.model_name}-${result.embedding_provider}`;
      const withKey = `${key}-with`;
      const withoutKey = `${key}-without`;

      const resultWithEvaluations: any = { ...result };

      // Add evaluation fields if they exist
      if (result.with_context) {
        const withEval = evaluations[withKey];
        if (withEval) {
          resultWithEvaluations.evaluation_with_context =
            evaluationToNumber(withEval);
        }
      }

      if (!result.with_context) {
        const withoutEval = evaluations[withoutKey];
        if (withoutEval) {
          resultWithEvaluations.evaluation_without_context =
            evaluationToNumber(withoutEval);
        }
      }

      return resultWithEvaluations;
    });

    // Create export object
    const exportData = {
      version: "1.1",
      exported_at: new Date().toISOString(),
      data: dataWithEvaluations,
      summary: {
        total_results: rawResults.length,
        total_evaluations: Object.keys(evaluations).length,
        evaluated_results: Math.floor(Object.keys(evaluations).length / 2),
      },
    };

    // Create and download file
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vision_rag_evaluations_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log("Exported data:", exportData.summary);
  }

  // Clear all evaluations
  function clearEvaluations() {
    if (
      confirm(
        "Are you sure you want to clear all evaluations? This action cannot be undone."
      )
    ) {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("llm-evaluations");
        // Notify all ResultRow components that evaluations were cleared
        window.dispatchEvent(new CustomEvent("evaluationsCleared"));
      }
      forceProgressUpdate(); // Force reactivity update
      alert("All evaluations have been cleared.");
    }
  }

  // Force progress update function
  function forceProgressUpdate() {
    evaluationUpdateTrigger++;
  }

  // Listen for evaluation changes from ResultRow components
  if (typeof window !== "undefined") {
    window.addEventListener("evaluationChanged", () => {
      forceProgressUpdate();
    });
  }

  // Check for evaluation changes periodically (reduced frequency since we have events)
  let lastEvaluationCount = 0;

  // Only run in browser environment
  if (typeof window !== "undefined") {
    setInterval(() => {
      const evaluationsJson = sessionStorage.getItem("llm-evaluations");
      const evaluations = evaluationsJson ? JSON.parse(evaluationsJson) : {};
      const currentCount = Object.keys(evaluations).length;

      if (currentCount !== lastEvaluationCount) {
        lastEvaluationCount = currentCount;
        evaluationUpdateTrigger++;
      }
    }, 1000); // Reduced to 1 second since we have events
  }

  // Data Grouping (Reactive)
  const groupedData = $derived(() => {
    const groups = new Map<string, GroupedResult>();

    for (const result of rawResults) {
      const key = `${result.validation_id}-${result.model_name}-${result.embedding_provider}`;

      if (!groups.has(key)) {
        groups.set(key, {
          id: key,
          validation_id: result.validation_id,
          model_name: result.model_name,
          embedding_provider: result.embedding_provider,
          image_url: result.image_url,
          real_question: result.real_question,
          crowd_majority: result.crowd_majority,
          with_context: null,
          without_context: null,
        });
      }

      const group = groups.get(key)!;
      if (result.with_context) {
        group.with_context = result;
      } else {
        group.without_context = result;
      }
    }

    return Array.from(groups.values());
  });

  // Unique Filter Options (Reactive)
  const modelOptions = $derived(() => {
    const models = new Set<string>();
    for (const result of rawResults) {
      models.add(result.model_name);
    }
    return Array.from(models).sort();
  });

  const embeddingOptions = $derived(() => {
    const embeddings = new Set<string>();
    for (const result of rawResults) {
      embeddings.add(result.embedding_provider);
    }
    return Array.from(embeddings).sort();
  });

  // Calculate context impact score for a result
  function calculateContextImpact(result: GroupedResult): number | null {
    try {
      // Only access sessionStorage in browser
      if (typeof sessionStorage === "undefined") return null;

      const stored = sessionStorage.getItem("llm-evaluations");
      if (!stored) return null;

      const evaluations = JSON.parse(stored);

      // Get evaluations for both responses
      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = evaluations[withKey];
      const withoutEval = evaluations[withoutKey];

      // Convert evaluations to numeric scores
      const getNumericScore = (evaluation: string | null): number | null => {
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
            return null; // No evaluation
        }
      };

      const withScore = getNumericScore(withEval);
      const withoutScore = getNumericScore(withoutEval);

      // If either evaluation is missing, return null
      if (withScore === null || withoutScore === null) return null;

      // Calculate the impact: (with_context_score - without_context_score)
      return withScore - withoutScore;
    } catch (e) {
      return null;
    }
  }

  // Check if a result has any evaluations
  function hasAnyEvaluations(result: GroupedResult): boolean {
    const impact = calculateContextImpact(result);
    return impact !== null;
  }

  // Filtering and data processing
  function filteredData() {
    let filtered = groupedData();

    // Apply model filter
    if (selectedModel !== "all") {
      filtered = filtered.filter((item) => item.model_name === selectedModel);
    }

    // Apply context filter
    if (selectedContext !== "all") {
      filtered = filtered.filter((item) => {
        if (selectedContext === "with_context") {
          return item.with_context !== null;
        } else if (selectedContext === "without_context") {
          return item.without_context !== null;
        }
        return true;
      });
    }

    // Apply embedding filter
    if (selectedEmbedding !== "all") {
      filtered = filtered.filter(
        (item) => item.embedding_provider === selectedEmbedding
      );
    }

    // Apply context impact filter
    if (selectedContextImpact !== "all") {
      filtered = filtered.filter((item) => {
        const impact = calculateContextImpact(item);
        switch (selectedContextImpact) {
          case "positive":
            return impact !== null && impact > 0;
          case "negative":
            return impact !== null && impact < 0;
          case "no_change":
            return impact !== null && impact === 0;
          case "evaluated":
            return hasAnyEvaluations(item);
          default:
            return true;
        }
      });
    }

    return filtered;
  }

  // Get visible data for table (with infinite scroll limit)
  function visibleData() {
    const allFiltered = filteredData();
    return allFiltered.slice(0, visibleItemsLimit);
  }

  // Get all filtered data for dashboard (no limits)
  function dashboardData() {
    return filteredData();
  }

  // Load more items for infinite scroll
  function loadMoreItems() {
    if (isLoadingMore) return;

    const totalAvailable = filteredData().length;
    if (visibleItemsLimit >= totalAvailable) return; // No more items to load

    isLoadingMore = true;

    // Simulate slight delay for better UX
    setTimeout(() => {
      visibleItemsLimit = Math.min(
        visibleItemsLimit + ITEMS_PER_LOAD,
        totalAvailable
      );
      isLoadingMore = false;
    }, 100);
  }

  // Calculate evaluation progress
  const evaluationProgress = $derived(() => {
    // This will trigger reactivity when evaluationUpdateTrigger changes
    evaluationUpdateTrigger;

    const allData = groupedData();
    const totalPossibleEvaluations = allData.length * 2; // 2 evaluations per result (with/without context)

    try {
      if (typeof sessionStorage === "undefined") {
        return { current: 0, total: totalPossibleEvaluations, percentage: 0 };
      }

      const stored = sessionStorage.getItem("llm-evaluations");
      if (!stored) {
        return { current: 0, total: totalPossibleEvaluations, percentage: 0 };
      }

      const evaluations = JSON.parse(stored);
      const completedEvaluations = Object.keys(evaluations).length;
      const percentage = Math.round(
        (completedEvaluations / totalPossibleEvaluations) * 100
      );

      return {
        current: completedEvaluations,
        total: totalPossibleEvaluations,
        percentage: Math.min(percentage, 100),
      };
    } catch (e) {
      return { current: 0, total: totalPossibleEvaluations, percentage: 0 };
    }
  });
</script>

<svelte:head>
  <title>Vision RAG Evaluation Viewer</title>
</svelte:head>

<main class="container">
  <header>
    <h1>Vision RAG Evaluation Viewer</h1>
    <p>
      Visual analysis tool for comparing model responses with and without
      context
    </p>
  </header>

  <!-- Tab Navigation -->
  <nav class="tab-nav">
    <button
      class="tab-btn"
      class:active={activeTab === "results"}
      onclick={() => (activeTab = "results")}
    >
      📊 Results
    </button>
    <button
      class="tab-btn"
      class:active={activeTab === "dashboard"}
      onclick={() => (activeTab = "dashboard")}
    >
      📈 Dashboard
    </button>
  </nav>

  <section class="controls">
    <div class="file-upload">
      <label for="file-input">Upload File:</label>
      <p class="upload-help">
        • Upload a <strong>.jsonl</strong> file with Vision RAG evaluation
        results<br />
        • Or upload a <strong>.json</strong> file with saved progress to continue
        evaluating
      </p>
      <input
        id="file-input"
        type="file"
        accept=".jsonl,.json"
        onchange={handleFileUpload}
      />
    </div>

    {#if rawResults.length > 0}
      <!-- Progress Stats -->
      <div class="progress-stats">
        <div class="progress-section">
          <strong>Progress:</strong>
          <div class="progress-bar">
            <div
              class="progress-bar-fill"
              style="width: {evaluationProgress().percentage}%"
            >
              {evaluationProgress().percentage}%
            </div>
          </div>
          <span
            >{evaluationProgress().current} of {evaluationProgress().total}
            evaluated</span
          >
        </div>

        <div class="evaluation-legend">
          <strong>Categories:</strong>
          <span class="category-mini">✅ Direct (3pts)</span>
          <span class="category-mini">💡 Inferable (2pts)</span>
          <span class="category-mini">❌ Missing (1pt)</span>
          <span class="category-mini">🤯 Hallucination (0pts)</span>
        </div>
      </div>

      <div class="action-buttons">
        <button class="btn btn-primary" onclick={exportEvaluations}>
          📥 Save Progress
        </button>
        <button class="btn btn-warning" onclick={clearEvaluations}>
          🗑️ Clear All Evaluations
        </button>
      </div>

      <div class="filters">
        <div class="filter-group">
          <label for="model-select">Model:</label>
          <select id="model-select" bind:value={selectedModel}>
            <option value="all">All Models</option>
            {#each modelOptions() as model}
              <option value={model}>{model}</option>
            {/each}
          </select>
        </div>

        <div class="filter-group">
          <label for="context-select">Context:</label>
          <select id="context-select" bind:value={selectedContext}>
            <option value="all">All</option>
            <option value="with_context">With Context</option>
            <option value="without_context">Without Context</option>
          </select>
        </div>

        <div class="filter-group">
          <label for="embedding-select">Embedding Provider:</label>
          <select id="embedding-select" bind:value={selectedEmbedding}>
            <option value="all">All Providers</option>
            {#each embeddingOptions() as embedding}
              <option value={embedding}>{embedding}</option>
            {/each}
          </select>
        </div>

        <div class="filter-group">
          <label for="context-impact-select">Context Impact:</label>
          <select id="context-impact-select" bind:value={selectedContextImpact}>
            <option value="all">All Results</option>
            <option value="positive">Positive Impact</option>
            <option value="negative">Negative Impact</option>
            <option value="no_change">No Change</option>
            <option value="evaluated">Has Evaluations</option>
          </select>
        </div>
      </div>

      <div class="stats">
        <p>Showing {visibleData().length} of {filteredData().length} results</p>
      </div>
    {/if}
  </section>

  <!-- Tab Content -->
  {#if activeTab === "results"}
    {#if rawResults.length > 0}
      <section class="results">
        <ResultsTable data={visibleData()} />

        <!-- Infinite Scroll Elements -->
        {#if visibleItemsLimit < filteredData().length}
          <!-- Loading indicator -->
          {#if isLoadingMore}
            <div class="loading-indicator">
              <div class="loading-spinner"></div>
              <span>Loading more results...</span>
            </div>
          {/if}

          <!-- Sentinel element for intersection observer -->
          <div bind:this={scrollSentinel} class="scroll-sentinel"></div>
        {:else if filteredData().length > 0}
          <div class="end-indicator">
            <span>All {filteredData().length} results loaded</span>
          </div>
        {/if}
      </section>
    {:else}
      <section class="empty-state">
        <p>No data loaded. Please upload a .jsonl file to get started.</p>
      </section>
    {/if}
  {:else if activeTab === "dashboard"}
    {#if rawResults.length > 0}
      <Dashboard data={dashboardData()} />
    {:else}
      <section class="empty-state">
        <p>
          No data loaded. Please upload a .jsonl file to see dashboard
          analytics.
        </p>
      </section>
    {/if}
  {/if}
</main>

<style>
  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      sans-serif;
  }

  header {
    text-align: center;
    margin-bottom: 2rem;
  }

  h1 {
    color: #333;
    margin-bottom: 0.5rem;
    font-size: 2.5rem;
    font-weight: 600;
  }

  header p {
    color: #666;
    font-size: 1.1rem;
  }

  .tab-nav {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 2rem;
    background-color: #f0f0f0;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .tab-btn {
    padding: 0.6rem 1.2rem;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    transition:
      background-color 0.2s,
      transform 0.1s;
    white-space: nowrap;
  }

  .tab-btn:hover {
    background-color: #e0e0e0;
  }

  .tab-btn.active {
    background-color: #007bff;
    color: white;
  }

  .tab-btn.active:hover {
    background-color: #0056b3;
  }

  .tab-btn:active {
    transform: scale(0.98);
  }

  .controls {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    border: 1px solid #e9ecef;
  }

  .file-upload {
    margin-bottom: 1.5rem;
  }

  .file-upload label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #333;
  }

  .file-upload input[type="file"] {
    padding: 0.5rem;
    border: 2px dashed #007bff;
    border-radius: 4px;
    background: white;
    width: 100%;
    cursor: pointer;
    transition: border-color 0.2s;
  }

  .file-upload input[type="file"]:hover {
    border-color: #0056b3;
  }

  .upload-help {
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 0.5rem;
    line-height: 1.4;
  }

  .upload-help strong {
    color: #333;
    font-weight: 600;
  }

  .action-buttons {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .btn {
    padding: 0.6rem 1rem;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    transition:
      background-color 0.2s,
      transform 0.1s;
  }

  .btn-primary {
    background-color: #007bff;
    color: white;
  }

  .btn-primary:hover {
    background-color: #0056b3;
  }

  .btn-warning {
    background-color: #ffc107;
    color: #212529;
  }

  .btn-warning:hover {
    background-color: #e0a800;
  }

  .btn:active {
    transform: scale(0.98);
  }

  .filters {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .filter-group {
    display: flex;
    flex-direction: column;
  }

  .filter-group label {
    margin-bottom: 0.25rem;
    font-weight: 500;
    color: #333;
    font-size: 0.9rem;
  }

  select {
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: white;
    font-size: 0.9rem;
    cursor: pointer;
    transition: border-color 0.2s;
  }

  select:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }

  .stats {
    text-align: center;
    color: #666;
    font-size: 0.9rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #e9ecef;
  }

  .results {
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: #666;
    background: #f8f9fa;
    border-radius: 8px;
    border: 2px dashed #ddd;
  }

  .empty-state p {
    font-size: 1.1rem;
  }

  .progress-stats {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    border: 1px solid #e9ecef;
    font-size: 0.85rem;
  }

  .progress-section {
    flex: 1;
    text-align: left;
  }

  .progress-section strong {
    font-weight: 600;
    color: #333;
    margin-right: 0.5rem;
  }

  .evaluation-legend {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-left: 1rem;
  }

  .category-mini {
    font-size: 0.75rem;
    color: #555;
    background-color: #e9ecef;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    border: 1px solid #dee2e6;
  }

  .progress-bar {
    background-color: #e9ecef;
    border-radius: 6px;
    height: 16px;
    width: 200px;
    overflow: hidden;
  }

  .progress-bar-fill {
    background: linear-gradient(90deg, #28a745, #20c997);
    height: 100%;
    transition: width 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 600;
    color: white;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  }

  .loading-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1rem;
    color: #666;
    font-size: 0.9rem;
  }

  .loading-spinner {
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3498db;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  .end-indicator {
    text-align: center;
    padding: 1rem;
    color: #666;
    font-size: 0.9rem;
  }

  .scroll-sentinel {
    height: 1px;
    width: 100%;
  }

  @media (max-width: 768px) {
    .container {
      padding: 1rem;
    }

    h1 {
      font-size: 2rem;
    }

    .filters {
      grid-template-columns: 1fr;
    }

    .progress-stats {
      flex-direction: column;
      gap: 0.5rem;
      padding: 0.5rem;
    }

    .evaluation-legend {
      margin-left: 0;
      flex-wrap: wrap;
      gap: 0.25rem;
    }

    .category-mini {
      font-size: 0.7rem;
      padding: 0.2rem 0.5rem;
    }

    .progress-bar {
      width: 100%;
      height: 14px;
    }

    .progress-bar-fill {
      font-size: 0.65rem;
    }

    .action-buttons {
      justify-content: center;
    }

    .loading-indicator {
      flex-direction: column;
      gap: 0.75rem;
      padding: 1.5rem 1rem;
    }

    .tab-nav {
      margin-bottom: 1rem;
      padding: 0.4rem 0.5rem;
    }

    .tab-btn {
      padding: 0.5rem 1rem;
      font-size: 0.9rem;
    }
  }
</style>
