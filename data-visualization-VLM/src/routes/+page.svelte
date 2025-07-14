<script lang="ts">
  import ResultsTable from "$lib/components/ResultsTable.svelte";
  import Dashboard from "$lib/components/Dashboard.svelte";
  import { onMount } from "svelte";
  import "$lib/styles/index.css";
  import type { 
    RawResult, 
    GroupedResult, 
    EvaluationProgress,
    TabType,
    ModelFilter,
    ContextFilter,
    EmbeddingFilter,
    ContextImpactFilter
  } from "$lib/types/index.js";
  import { INFINITE_SCROLL_CONFIG } from "$lib/types/index.js";

  // State variables
  let rawResults: RawResult[] = $state([]);
  let selectedModel: ModelFilter = $state("all");
  let selectedContext: ContextFilter = $state("all");
  let selectedEmbedding: EmbeddingFilter = $state("all");
  let selectedContextImpact: ContextImpactFilter = $state("all");
  
  // Column visibility state
  let columnVisibility = $state({
    id: true,
    contextImages: true,
    withContext: true,
    withoutContext: true,
    score: true,
    contextImpact: true
  });
  
  // UI state
  let showFilters = $state(false);
  let activeTab: TabType = $state("results");

  // Infinite scroll state
  let visibleItemsLimit: number = $state(INFINITE_SCROLL_CONFIG.INITIAL_LIMIT);
  let isLoadingMore = $state(false);
  let scrollSentinel: HTMLElement | undefined; // Element to observe for intersection
  let showAllItems = $state(false); // Toggle to show all items at once

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
        rootMargin: INFINITE_SCROLL_CONFIG.ROOT_MARGIN,
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
    visibleItemsLimit = INFINITE_SCROLL_CONFIG.INITIAL_LIMIT;
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

            // Extract evaluations based on the result's context type
            if (result.with_context) {
              // This is a with_context result
              if (result.evaluation_with_context !== undefined) {
                const withKey = `${key}-with`;
                const evaluation = numberToEvaluation(
                  result.evaluation_with_context
                );
                if (evaluation) {
                  evaluations[withKey] = evaluation;
                }
              }
            } else {
              // This is a without_context result
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

    // Helper function to count words in a string
    function countWords(text: string): number {
      return text
        .trim()
        .split(/\s+/)
        .filter((word) => word.length > 0).length;
    }

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

    // Convert evaluation strings to category index (0-3)
    const evaluationToCategory = (evaluation: string | null): number | null => {
      switch (evaluation) {
        case "directly_answered":
          return 0; // Direct (3pts)
        case "inferable":
          return 1; // Inferable (2pts)
        case "missing_incorrect":
          return 2; // Missing (1pt)
        case "hallucination":
          return 3; // Hallucination (0pts)
        default:
          return null;
      }
    };

    // Calculate correctness score for a result
    const calculateCorrectnessScore = (result: any): number | null => {
      const key = `${result.validation_id}-${result.model_name}-${result.embedding_provider}`;
      const withKey = `${key}-with`;
      const withoutKey = `${key}-without`;

      const withEval = evaluations[withKey];
      const withoutEval = evaluations[withoutKey];

      const withScore = evaluationToNumber(withEval);
      const withoutScore = evaluationToNumber(withoutEval);

      const totalScore = (withScore || 0) + (withoutScore || 0);
      const evaluatedCount =
        (withScore !== null ? 1 : 0) + (withoutScore !== null ? 1 : 0);

      if (evaluatedCount === 0) return null;

      return totalScore / evaluatedCount;
    };

    // Calculate context impact for a result
    const calculateContextImpactForResult = (result: any): number | null => {
      const key = `${result.validation_id}-${result.model_name}-${result.embedding_provider}`;
      const withKey = `${key}-with`;
      const withoutKey = `${key}-without`;

      const withEval = evaluations[withKey];
      const withoutEval = evaluations[withoutKey];

      const withScore = evaluationToNumber(withEval);
      const withoutScore = evaluationToNumber(withoutEval);

      if (withScore === null || withoutScore === null) return null;

      return withScore - withoutScore;
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
          resultWithEvaluations.category_with_context =
            evaluationToCategory(withEval);
        }
        // Always add word count for with context responses
        resultWithEvaluations.word_count_with_context = countWords(
          result.llm_response
        );
      }

      if (!result.with_context) {
        const withoutEval = evaluations[withoutKey];
        if (withoutEval) {
          resultWithEvaluations.evaluation_without_context =
            evaluationToNumber(withoutEval);
          resultWithEvaluations.category_without_context =
            evaluationToCategory(withoutEval);
        }
        // Always add word count for without context responses
        resultWithEvaluations.word_count_without_context = countWords(
          result.llm_response
        );
      }

      // Add calculated scores
      resultWithEvaluations.correctness_score =
        calculateCorrectnessScore(result);
      resultWithEvaluations.context_impact =
        calculateContextImpactForResult(result);

      return resultWithEvaluations;
    });

    // Create export object
    const exportData = {
      version: "1.2",
      exported_at: new Date().toISOString(),
      legend: {
        categories: {
          0: "Direct (3pts)",
          1: "Inferable (2pts)",
          2: "Missing (1pt)",
          3: "Hallucination (0pts)",
        },
        fields: {
          evaluation_with_context:
            "Numeric score for with context response (0-3)",
          evaluation_without_context:
            "Numeric score for without context response (0-3)",
          category_with_context:
            "Category index for with context response (0-3)",
          category_without_context:
            "Category index for without context response (0-3)",
          word_count_with_context: "Word count for with context response",
          word_count_without_context: "Word count for without context response",
          correctness_score: "Average correctness score (0-3)",
          context_impact:
            "Context impact score (with_context - without_context)",
        },
      },
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
    if (showAllItems) {
      return allFiltered; // Show all items when toggle is enabled
    }
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
      const newLimit = Math.min(
        visibleItemsLimit + INFINITE_SCROLL_CONFIG.ITEMS_PER_LOAD,
        totalAvailable
      );
      visibleItemsLimit = newLimit;
      isLoadingMore = false;
    }, 100);
  }

  // Calculate evaluation progress
  const evaluationProgress = $derived(() => {
    // This will trigger reactivity when evaluationUpdateTrigger changes
    evaluationUpdateTrigger;

    const allData = groupedData();

    // Count actual possible evaluations based on available data
    let totalPossibleEvaluations = 0;
    for (const result of allData) {
      if (result.with_context) totalPossibleEvaluations++;
      if (result.without_context) totalPossibleEvaluations++;
    }

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

<style>
  .app-layout {
    display: flex;
    min-height: 100vh;
    gap: 20px;
    padding: 20px;
  }

  .floating-sidebar {
    flex: 0 0 280px;
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 20px;
    height: fit-content;
    position: sticky;
    top: 20px;
  }

  .main-content {
    flex: 1;
    min-height: 100vh;
  }

  .sidebar-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 16px;
    color: #333;
  }

  .filter-group {
    margin-bottom: 16px;
  }

  .filter-group label {
    display: block;
    margin-bottom: 4px;
    font-weight: 500;
    color: #555;
  }

  .filter-group select {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: white;
  }

  /* Responsive behavior */
  @media (max-width: 1200px) {
    .floating-sidebar {
      flex: 0 0 240px;
    }
  }

  @media (max-width: 1024px) {
    .floating-sidebar {
      flex: 0 0 200px;
    }
  }

  @media (max-width: 768px) {
    .app-layout {
      flex-direction: column;
    }
    
    .floating-sidebar {
      flex: none;
      position: relative;
      top: 0;
    }
  }

  .container {
    width: 100%;
    padding: 20px;
  }

  /* Column Visibility Controls */
  .column-toggles {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .column-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    transition: background-color 0.2s ease;
  }

  .column-toggle:hover {
    background-color: #f1f3f4;
  }

  .column-toggle input[type="checkbox"] {
    margin: 0;
    cursor: pointer;
  }

  .column-toggle span {
    color: #555;
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .column-toggles {
      gap: 0.375rem;
    }

    .column-toggle {
      font-size: 0.85rem;
      padding: 0.2rem;
    }
  }
</style>

<div class="app-layout">
  <!-- Floating Sidebar -->
  <aside class="floating-sidebar">
    <h2 class="sidebar-title">Filters</h2>
    
    {#if rawResults.length > 0}
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

      <!-- Column Visibility Controls -->
      <div class="filter-group">
        <label>Column Visibility:</label>
        <div class="column-toggles">
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.id} />
            <span>ID & Details</span>
          </label>
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.contextImages} />
            <span>Retrieved Visually Similar Images</span>
          </label>
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.withContext} />
            <span>With Context</span>
          </label>
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.withoutContext} />
            <span>Without Context</span>
          </label>
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.score} />
            <span>Score</span>
          </label>
          <label class="column-toggle">
            <input type="checkbox" bind:checked={columnVisibility.contextImpact} />
            <span>Context Impact</span>
          </label>
        </div>
      </div>
    {:else}
      <p style="color: #666; font-size: 0.9rem;">Upload data to see filters</p>
    {/if}
  </aside>

  <!-- Main Content -->
  <div class="main-content">
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

          <div class="stats">
            <p>Showing {visibleData().length} of {filteredData().length} results</p>
            <div class="display-options">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  bind:checked={showAllItems}
                  onchange={() => {
                    if (showAllItems) {
                      // When enabling show all, disconnect the observer
                      if (observer && scrollSentinel) {
                        observer.unobserve(scrollSentinel);
                      }
                    } else {
                      // When disabling show all, reset to initial limit and reconnect observer
                      visibleItemsLimit = INFINITE_SCROLL_CONFIG.INITIAL_LIMIT;
                      if (observer && scrollSentinel) {
                        observer.observe(scrollSentinel);
                      }
                    }
                  }}
                />
                Show all items at once (disable infinite scroll)
              </label>
            </div>
          </div>
        {/if}
      </section>

      <!-- Tab Content -->
      {#if activeTab === "results"}
        {#if rawResults.length > 0}
          <section class="results">
            <ResultsTable data={visibleData()} {columnVisibility} />

            <!-- Infinite Scroll Elements (only show when not showing all items) -->
            {#if !showAllItems}
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
  </div>
</div>
