<script lang="ts">
  import ResultRow from "./ResultRow.svelte";

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
  let { 
    data = [],
    fullDataset = null,
    columnVisibility = {
      id: true,
      contextImages: true,
      withContext: true,
      withoutContext: true,
      score: true,
      contextImpact: true
    }
  }: { 
    data: GroupedResult[];
    fullDataset?: GroupedResult[] | null;
    columnVisibility?: {
      id: boolean;
      contextImages: boolean;
      withContext: boolean;
      withoutContext: boolean;
      score: boolean;
      contextImpact: boolean;
    };
  } = $props();

  // Sorting state
  type SortField =
    | "processing_time_with"
    | "processing_time_without"
    | "validation_id"
    | "model_name"
    | "correctness_score"
    | "context_impact";
  type SortDirection = "asc" | "desc" | null;

  let sortField: SortField | null = $state(null);
  let sortDirection: SortDirection = $state(null);

  // Derived sorted data
  let sortedData = $derived.by(() => {
    if (!sortField || !sortDirection) return data;

    const sorted = [...data].sort((a, b) => {
      let aValue: number | string;
      let bValue: number | string;

      switch (sortField) {
        case "processing_time_with":
          aValue = a.with_context?.processing_time ?? Number.MAX_SAFE_INTEGER;
          bValue = b.with_context?.processing_time ?? Number.MAX_SAFE_INTEGER;
          break;
        case "processing_time_without":
          aValue =
            a.without_context?.processing_time ?? Number.MAX_SAFE_INTEGER;
          bValue =
            b.without_context?.processing_time ?? Number.MAX_SAFE_INTEGER;
          break;
        case "validation_id":
          aValue = parseInt(a.validation_id, 10);
          bValue = parseInt(b.validation_id, 10);
          break;
        case "model_name":
          aValue = a.model_name;
          bValue = b.model_name;
          break;
        case "correctness_score":
          aValue = getCorrectnessScore(a);
          bValue = getCorrectnessScore(b);
          break;
        case "context_impact":
          aValue = getContextImpactScore(a);
          bValue = getContextImpactScore(b);
          break;
        default:
          return 0;
      }

      if (typeof aValue === "string" && typeof bValue === "string") {
        return sortDirection === "asc"
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      return sortDirection === "asc"
        ? (aValue as number) - (bValue as number)
        : (bValue as number) - (aValue as number);
    });

    return sorted;
  });

  // Sort handler
  function handleSort(field: SortField) {
    if (sortField === field) {
      // Cycle through: asc -> desc -> null
      if (sortDirection === "asc") {
        sortDirection = "desc";
      } else if (sortDirection === "desc") {
        sortField = null;
        sortDirection = null;
      }
    } else {
      sortField = field;
      sortDirection = "asc";
    }
  }

  // Get sort icon
  function getSortIcon(field: SortField): string {
    if (sortField !== field) return "↕️";
    return sortDirection === "asc" ? "⬆️" : "⬇️";
  }

  // Calculate conciseness penalty for a response
  function getConcisenessPenalty(response: string): number {
    if (!response) return 0;

    const wordCount = response.trim().split(/\s+/).length;

    // Ideal range: 10-50 words (no penalty)
    if (wordCount >= 10 && wordCount <= 50) {
      return 0; // No penalty
    }

    // Short responses (less than 10 words) - small penalty
    if (wordCount < 10) {
      return 0.1; // Small penalty for being too brief
    }

    // Long responses - increasing penalty
    if (wordCount <= 100) {
      return 0.2; // Moderate penalty for moderate verbosity
    } else if (wordCount <= 150) {
      return 0.4; // Higher penalty for high verbosity
    } else {
      return 0.6; // Maximum penalty for excessive verbosity
    }
  }

  // Calculate correctness score including conciseness for a result
  function getCorrectnessScore(result: GroupedResult): number {
    try {
      const stored = sessionStorage.getItem("llm-evaluations");
      if (!stored) return 0;

      const evaluations = JSON.parse(stored);

      // Calculate score for both responses
      const withKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-with`;
      const withoutKey = `${result.validation_id}-${result.model_name}-${result.embedding_provider}-without`;

      const withEval = evaluations[withKey];
      const withoutEval = evaluations[withoutKey];

      // Convert evaluations to numeric scores
      const getNumericScore = (evaluation: string | null): number => {
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
            return -1; // No evaluation = lowest priority
        }
      };

      const withScore = getNumericScore(withEval);
      const withoutScore = getNumericScore(withoutEval);

      // Calculate base correctness score
      const totalScore = withScore + withoutScore;
      const evaluatedCount =
        (withScore >= 0 ? 1 : 0) + (withoutScore >= 0 ? 1 : 0);

      if (evaluatedCount === 0) return -1; // No evaluations

      const correctnessScore = totalScore / evaluatedCount;

      // Return just the correctness score (3.0 scale)
      return correctnessScore;
    } catch (e) {
      return 0;
    }
  }

  // Calculate context impact score for a result
  function getContextImpactScore(result: GroupedResult): number {
    try {
      const stored = sessionStorage.getItem("llm-evaluations");
      if (!stored) return 0;

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

      // If either evaluation is missing, return 0 (neutral impact)
      if (withScore === null || withoutScore === null) return 0;

      // Calculate the impact: (with_context_score - without_context_score)
      return withScore - withoutScore;
    } catch (e) {
      return 0;
    }
  }
</script>

<div class="table-container">
  <table class="results-table">
    <thead>
      <tr>
        {#if columnVisibility.id}
          <th
            class="sortable col-id"
            class:sorted={sortField === "validation_id"}
            onclick={() => handleSort("validation_id")}
          >
            Query Entry Details
            {#if sortField === "validation_id"}
              <span class="sort-arrow">{sortDirection === "asc" ? "↑" : "↓"}</span
              >
            {/if}
          </th>
        {/if}
        {#if columnVisibility.contextImages}
          <th class="col-context-images">Retrieved Visually Similar Images</th>
        {/if}
        {#if columnVisibility.withContext}
          <th class="col-with-context">With Context</th>
        {/if}
        {#if columnVisibility.withoutContext}
          <th class="col-without-context">Without Context</th>
        {/if}
        {#if columnVisibility.score}
          <th
            class="sortable col-score"
            class:sorted={sortField === "correctness_score"}
            onclick={() => handleSort("correctness_score")}
            title="Content accuracy score based on evaluation (3=Direct, 2=Inferable, 1=Missing, 0=Hallucination)"
          >
            Score
            {#if sortField === "correctness_score"}
              <span class="sort-arrow">{sortDirection === "asc" ? "↑" : "↓"}</span
              >
            {/if}
          </th>
        {/if}
        {#if columnVisibility.contextImpact}
          <th
            class="sortable col-context-impact"
            class:sorted={sortField === "context_impact"}
            onclick={() => handleSort("context_impact")}
          >
            Context Impact
            {#if sortField === "context_impact"}
              <span class="sort-arrow">{sortDirection === "asc" ? "↑" : "↓"}</span
              >
            {/if}
          </th>
        {/if}
      </tr>
    </thead>
    <tbody>
      {#each sortedData as result, index (result.id)}
        <ResultRow {result} allResults={data} {fullDataset} {columnVisibility} rowNumber={index + 1} />
      {/each}
    </tbody>
  </table>

  {#if data.length === 0}
    <div class="no-results">
      <p>No results match the current filters.</p>
    </div>
  {:else if sortField}
    <div class="sort-info">
      <span
        >Sorted by:
        {sortField === "processing_time_with"
          ? "Processing Time (With Context)"
          : sortField === "processing_time_without"
            ? "Processing Time (Without Context)"
            : sortField === "validation_id"
              ? "Validation ID"
              : sortField === "model_name"
                ? "Model Name"
                : sortField === "correctness_score"
                  ? "Correctness Score"
                  : sortField === "context_impact"
                    ? "Context Impact"
                    : "Unknown"}
        ({sortDirection === "asc" ? "ascending" : "descending"})
      </span>
      <button
        class="clear-sort"
        onclick={() => {
          sortField = null;
          sortDirection = null;
        }}
      >
        Clear Sort
      </button>
    </div>
  {/if}
</div>

<style>
  .table-container {
    width: 100%;
    /* Remove overflow-x: auto to prevent horizontal scrolling */
  }

  .results-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    background: white;
    table-layout: auto; /* Changed from fixed to auto for flexible columns */
  }

  .results-table thead th {
    background: #f8f9fa;
    color: #333;
    font-weight: 600;
    padding: 0.7rem 0.6rem;
    text-align: left;
    border-bottom: 2px solid #e9ecef;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .results-table thead th.sortable {
    cursor: pointer;
    user-select: none;
    transition: background-color 0.2s ease;
  }

  .results-table thead th.sortable:hover {
    background: #e9ecef;
  }

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .sort-icon {
    font-size: 0.8rem;
    opacity: 0.6;
    min-width: 20px;
    text-align: center;
  }

  .results-table thead th.sortable:hover .sort-icon {
    opacity: 1;
  }

  .results-table thead th.sorted {
    background: #d4edda;
    color: #155724;
  }

  .results-table thead th.sorted .sort-icon {
    opacity: 1;
    font-weight: bold;
  }

  /* Flexible column widths - percentages instead of fixed pixels */
  .col-id {
    width: 10%; /* Increased from 8% to accommodate details content */
    min-width: 120px; /* Increased from 60px */
    box-sizing: border-box;
  }

  .col-details {
    width: 15%;
    min-width: 180px;
    box-sizing: border-box;
  }

  .col-context-images {
    width: 20%; /* Reduced from 23% */
    min-width: 220px; /* Reduced from 240px */
    box-sizing: border-box;
  }

  .col-with-context {
    width: 22%; /* Reduced from 25% */
    min-width: 230px; /* Reduced from 250px */
    box-sizing: border-box;
  }

  .col-without-context {
    width: 22%; /* Reduced from 25% */
    min-width: 230px; /* Reduced from 250px */
    box-sizing: border-box;
  }

  .col-score {
    width: 6%;
    min-width: 50px;
    text-align: center;
    box-sizing: border-box;
  }

  .col-context-impact {
    width: 8%;
    min-width: 70px;
    text-align: center;
    box-sizing: border-box;
  }

  .no-results {
    text-align: center;
    padding: 2rem;
    color: #666;
    font-style: italic;
  }

  .sort-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: #e3f2fd;
    border: 1px solid #bbdefb;
    border-radius: 4px;
    margin-top: 0.75rem;
    font-size: 0.8rem;
    color: #1565c0;
  }

  .clear-sort {
    background: #1976d2;
    color: white;
    border: none;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
    transition: background-color 0.2s ease;
  }

  .clear-sort:hover {
    background: #1565c0;
  }

  th,
  td {
    border: 1px solid #ddd;
    padding: 0.6rem;
    text-align: left;
    vertical-align: top;
    font-size: 0.85rem;
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    white-space: normal;
    overflow: hidden;
    max-width: 0; /* Forces table to respect percentage widths */
  }

  /* Responsive adjustments */
  @media (max-width: 1400px) {
    .results-table {
      font-size: 0.85rem;
    }
    
    .col-id {
      min-width: 200px;
    }
    
    .col-context-images,
    .col-with-context,
    .col-without-context {
      min-width: 200px;
    }
  }

  @media (max-width: 1200px) {
    .results-table {
      font-size: 0.8rem;
    }

    .col-id {
      min-width: 180px;
    }

    .col-details {
      min-width: 160px;
    }
    
    .col-context-images,
    .col-with-context,
    .col-without-context {
      min-width: 180px;
    }
  }

  @media (max-width: 768px) {
    .results-table thead th {
      padding: 0.5rem 0.4rem;
    }

    .header-content {
      gap: 0.25rem;
    }

    .sort-icon {
      font-size: 0.7rem;
      min-width: 16px;
    }

    .col-id {
      min-width: 160px; /* Increased to accommodate combined content */
    }

    .col-details {
      min-width: 140px;
    }

    .col-context-images,
    .col-with-context,
    .col-without-context {
      min-width: 160px;
    }

    .col-score {
      min-width: 45px;
    }

    .col-context-impact {
      min-width: 60px;
    }

    .sort-info {
      flex-direction: column;
      gap: 0.5rem;
      align-items: flex-start;
      padding: 0.5rem;
    }

    .sort-info span {
      font-size: 0.8rem;
    }
  }
</style>
