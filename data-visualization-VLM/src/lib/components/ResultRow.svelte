<script lang="ts">
  import ImageModal from "./ImageModal.svelte";

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

  interface ImageData {
    url: string;
    alt: string;
    title?: string;
  }

  // Props
  let {
    result,
    allResults,
  }: { result: GroupedResult; allResults: GroupedResult[] } = $props();

  // Modal state
  let isModalOpen = $state(false);
  let modalImages: ImageData[] = $state([]);
  let currentImageIndex = $state(0);

  // Text expansion state
  let isWithContextExpanded = $state(false);
  let isWithoutContextExpanded = $state(false);

  // Evaluation types
  type EvaluationType =
    | "directly_answered"
    | "inferable"
    | "missing_incorrect"
    | "hallucination"
    | null;

  // Evaluation state - read directly from sessionStorage each time
  function getStoredEvaluations(): Record<string, EvaluationType> {
    if (typeof window === "undefined") return {};

    try {
      const stored = sessionStorage.getItem("llm-evaluations");
      return stored ? JSON.parse(stored) : {};
    } catch (e) {
      console.warn("Failed to parse stored evaluations");
      return {};
    }
  }

  // Save evaluations to sessionStorage
  function saveEvaluations(evaluations: Record<string, EvaluationType>) {
    if (typeof window === "undefined") return;

    try {
      sessionStorage.setItem("llm-evaluations", JSON.stringify(evaluations));
    } catch (e) {
      console.warn("Failed to save evaluations");
    }
  }

  // Listen for storage changes from other components/tabs
  let storageUpdateTrigger = $state(0);

  if (typeof window !== "undefined") {
    // Listen for storage events (when storage changes from other tabs/components)
    window.addEventListener("storage", () => {
      storageUpdateTrigger++;
    });

    // Also listen for custom events from within the same tab
    window.addEventListener("evaluationsCleared", () => {
      storageUpdateTrigger++;
    });
  }

  // Generate unique key for each response
  function getResponseKey(withContext: boolean): string {
    return `${result.validation_id}-${result.model_name}-${result.embedding_provider}-${withContext ? "with" : "without"}`;
  }

  // Set evaluation for a response
  function setEvaluation(withContext: boolean, evaluation: EvaluationType) {
    const evaluations = getStoredEvaluations();
    const key = getResponseKey(withContext);

    if (evaluations[key] === evaluation) {
      // If clicking the same evaluation, remove it
      evaluations[key] = null;
      delete evaluations[key];
    } else {
      evaluations[key] = evaluation;
    }

    // Save back to sessionStorage
    saveEvaluations(evaluations);

    // Trigger reactivity update
    storageUpdateTrigger++;

    // Dispatch custom event to notify other components
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("evaluationChanged"));
    }
  }

  // Get current evaluation for a response (reactive)
  function getEvaluation(withContext: boolean): EvaluationType {
    // This will trigger reactivity when storageUpdateTrigger changes
    storageUpdateTrigger;

    const evaluations = getStoredEvaluations();
    const key = getResponseKey(withContext);
    return evaluations[key] || null;
  }

  // Get evaluation button class
  function getEvaluationClass(
    withContext: boolean,
    type: EvaluationType
  ): string {
    const current = getEvaluation(withContext);
    return current === type ? "active" : "";
  }

  // Calculate correctness score for display
  function getCorrectnessScore(): number {
    const withEval = getEvaluation(true);
    const withoutEval = getEvaluation(false);

    const getNumericScore = (evaluation: EvaluationType): number => {
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
          return -1; // No evaluation
      }
    };

    const withScore = getNumericScore(withEval);
    const withoutScore = getNumericScore(withoutEval);

    const totalScore = withScore + withoutScore;
    const evaluatedCount =
      (withScore >= 0 ? 1 : 0) + (withoutScore >= 0 ? 1 : 0);

    if (evaluatedCount === 0) return -1; // No evaluations
    return totalScore / evaluatedCount;
  }

  // Calculate context impact score
  function getContextImpactScore(): number | null {
    const withEval = getEvaluation(true);
    const withoutEval = getEvaluation(false);

    const getNumericScore = (evaluation: EvaluationType): number | null => {
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

    // If either evaluation is missing, return null for display purposes
    if (withScore === null || withoutScore === null) return null;

    // Calculate the impact: (with_context_score - without_context_score)
    return withScore - withoutScore;
  }

  // Get context impact description
  function getContextImpactDescription(score: number | null): string {
    if (score === null) return "Not evaluated";

    if (score === 3) return "Major Improvement";
    if (score === 2) return "Significant Improvement";
    if (score === 1) return "Minor Improvement";
    if (score === 0) return "No Change";
    if (score === -1) return "Minor Degradation";
    if (score === -2) return "Major Degradation";
    if (score === -3) return "Catastrophic Failure";

    // Handle other cases
    if (score > 0) return "Improvement";
    return "Degradation";
  }

  // Get context impact color
  function getContextImpactColor(score: number | null): string {
    if (score === null) return "#999";

    if (score >= 2) return "#28a745"; // Green for major improvements
    if (score === 1) return "#17a2b8"; // Blue for minor improvements
    if (score === 0) return "#6c757d"; // Gray for no change
    if (score === -1) return "#ffc107"; // Yellow for minor degradation
    if (score <= -2) return "#dc3545"; // Red for major degradation

    return "#6c757d";
  }

  // Reactive context impact score
  let contextImpactScore = $derived(getContextImpactScore());

  // Format score for display
  function formatScore(score: number): string {
    if (score < 0) return "-";
    return score.toFixed(1);
  }

  // Get score color
  function getScoreColor(score: number): string {
    if (score < 0) return "#999";
    if (score >= 2.5) return "#28a745"; // Green for excellent scores (directly answered)
    if (score >= 2.0) return "#17a2b8"; // Blue for good scores (inferable)
    if (score >= 1.0) return "#ffc107"; // Yellow for medium scores (missing/incorrect)
    return "#dc3545"; // Red for poor scores (hallucination)
  }

  function formatProcessingTime(time: number): string {
    return `${time.toFixed(2)}s`;
  }

  // Calculate time statistics for visualization
  function getTimeStats() {
    const allTimes: number[] = [];

    allResults.forEach((res) => {
      if (res.with_context?.processing_time) {
        allTimes.push(res.with_context.processing_time);
      }
      if (res.without_context?.processing_time) {
        allTimes.push(res.without_context.processing_time);
      }
    });

    if (allTimes.length === 0) return { min: 0, max: 10, avg: 5 };

    const min = Math.min(...allTimes);
    const max = Math.max(...allTimes);
    const avg = allTimes.reduce((sum, time) => sum + time, 0) / allTimes.length;

    return { min, max, avg };
  }

  // Get visual properties for processing time bar
  function getTimeBarProps(time: number) {
    const { min, max, avg } = getTimeStats();

    // Calculate width as percentage (0-100%)
    const width = Math.min(100, (time / max) * 100);

    // Determine color based on time relative to average
    let color = "#28a745"; // Green for fast
    if (time > avg * 1.5) {
      color = "#dc3545"; // Red for slow
    } else if (time > avg * 1.2) {
      color = "#ffc107"; // Yellow for medium
    }

    return { width, color };
  }

  function truncateText(text: string, maxLength: number = 150): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  }

  function shouldShowExpandButton(
    text: string,
    maxLength: number = 150
  ): boolean {
    return typeof text === "string" && text.length > maxLength;
  }

  function getDisplayText(
    text: string,
    isExpanded: boolean,
    maxLength: number = 150
  ): string {
    if (!text) return "";
    if (isExpanded || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  }

  function toggleWithContextExpansion() {
    // Save current scroll position
    const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;

    isWithContextExpanded = !isWithContextExpanded;

    // Restore scroll position after DOM update
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        window.scrollTo({
          top: currentScrollY,
          behavior: "instant",
        });
      });
    }
  }

  function toggleWithoutContextExpansion() {
    // Save current scroll position
    const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;

    isWithoutContextExpanded = !isWithoutContextExpanded;

    // Restore scroll position after DOM update
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        window.scrollTo({
          top: currentScrollY,
          behavior: "instant",
        });
      });
    }
  }

  // Open modal with query image
  function openQueryImageModal() {
    modalImages = [
      {
        url: result.image_url,
        alt: `Query image for validation ${result.validation_id}`,
        title: `Query Image - ${result.real_question}`,
      },
    ];
    currentImageIndex = 0;
    isModalOpen = true;
  }

  // Open modal with specific context image
  function openContextImageModal(imageUrl: string, index: number) {
    if (result.with_context && result.with_context.similar_images) {
      modalImages = result.with_context.similar_images.map((img, i) => ({
        url: img.image_url,
        alt: `Context image ${i + 1}`,
        title: `Context Image ${i + 1} of ${result.with_context!.similar_images.length}`,
      }));
      currentImageIndex = index;
      isModalOpen = true;
    }
  }

  // Calculate distance color and properties for visual representation
  function getDistanceProps(distance: number, allDistances: number[]) {
    if (allDistances.length === 0)
      return { color: "#6c757d", label: "Unknown", rawDistance: distance };

    // Color scale based on distance value (lower = better, so green for low values)
    let color: string;
    let label: string;

    if (distance <= 0.5) {
      color = "#28a745"; // Green - very similar
      label = "Very Similar";
    } else if (distance <= 1.0) {
      color = "#17a2b8"; // Blue - similar
      label = "Similar";
    } else if (distance <= 1.5) {
      color = "#ffc107"; // Yellow - moderate
      label = "Moderate";
    } else {
      color = "#dc3545"; // Red - poor
      label = "Poor";
    }

    return {
      color,
      label,
      rawDistance: distance,
    };
  }

  // Get all distances for the current context images to calculate relative similarity
  function getAllDistances(): number[] {
    if (!result.with_context?.similar_images) return [];
    return result.with_context.similar_images.map((img) => img.distance);
  }

  // Format distance for display
  function formatDistance(distance: number): string {
    return distance.toFixed(3);
  }

  // Extract meaningful keywords from text
  function extractKeywords(text: string): string[] {
    if (!text) return [];

    // Common stop words to exclude
    const stopWords = new Set([
      "the",
      "a",
      "an",
      "and",
      "or",
      "but",
      "in",
      "on",
      "at",
      "to",
      "for",
      "of",
      "with",
      "by",
      "is",
      "are",
      "was",
      "were",
      "be",
      "been",
      "have",
      "has",
      "had",
      "do",
      "does",
      "did",
      "will",
      "would",
      "could",
      "should",
      "may",
      "might",
      "can",
      "this",
      "that",
      "these",
      "those",
      "i",
      "you",
      "he",
      "she",
      "it",
      "we",
      "they",
      "me",
      "him",
      "her",
      "us",
      "them",
      "my",
      "your",
      "his",
      "her",
      "its",
      "our",
      "their",
      "what",
      "where",
      "when",
      "why",
      "how",
      "who",
      "which",
    ]);

    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, " ") // Remove punctuation
      .split(/\s+/) // Split by whitespace
      .filter((word) => word.length > 2 && !stopWords.has(word)) // Filter meaningful words
      .slice(0, 10); // Limit to prevent too much highlighting
  }

  // Get all keywords to highlight for this result
  function getHighlightKeywords(): string[] {
    // Only highlight keywords from the expected answer (crowd_majority)
    return extractKeywords(result.crowd_majority);
  }

  // Highlight keywords in text
  function highlightKeywords(text: string): string {
    if (!text) return "";

    const keywords = getHighlightKeywords();
    if (keywords.length === 0) return text;

    let highlightedText = text;

    keywords.forEach((keyword) => {
      const regex = new RegExp(`\\b${keyword}\\b`, "gi");
      highlightedText = highlightedText.replace(
        regex,
        `<mark class="keyword-highlight">$&</mark>`
      );
    });

    return highlightedText;
  }
</script>

<tr class="result-row">
  <!-- ID with Query Image -->
  <td class="col-id">
    <div class="id-content">
      <span class="validation-id">#{result.validation_id}</span>

      <!-- Query Image -->
      <div class="image-container">
        <button
          class="image-button"
          onclick={openQueryImageModal}
          aria-label="View query image in full size"
        >
          <img
            src={result.image_url}
            alt="Validation {result.validation_id}"
            class="query-image clickable-image"
            loading="lazy"
          />
          <div class="image-overlay">
            <svg
              class="expand-icon"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M15 3H21M21 3V9M21 3L15 9M9 21H3M3 21V15M3 21L9 15"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
        </button>
      </div>
    </div>
  </td>

  <!-- Details (including model info) -->
  <td class="col-details">
    <div class="details-content">
      <div class="detail-item">
        <strong>Model:</strong>
        <div class="model-info">
          <div class="model-name">{result.model_name}</div>
          <div class="embedding-provider">{result.embedding_provider}</div>
        </div>
      </div>
      <div class="detail-item">
        <strong>Question:</strong>
        <p class="question-text">{result.real_question}</p>
      </div>
      <div class="detail-item">
        <strong>Expected Answer:</strong>
        <p class="answer-text">{result.crowd_majority}</p>
      </div>
    </div>
  </td>

  <!-- Context Images -->
  <td class="col-context-images">
    <div class="context-images">
      {#if result.with_context && result.with_context.similar_images && result.with_context.similar_images.length > 0}
        <div class="similar-images-list">
          {#each result.with_context.similar_images.slice(0, 4) as similarImage, index}
            <div class="similar-image-item">
              <button
                class="context-image-button"
                onclick={() =>
                  openContextImageModal(similarImage.image_url, index)}
                aria-label="View context image {index + 1} in full size"
              >
                <img
                  src={similarImage.image_url}
                  alt="Context {index + 1}"
                  class="similar-image clickable-image"
                  loading="lazy"
                />
                <div class="image-overlay small">
                  <svg
                    class="expand-icon"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M15 3H21M21 3V9M21 3L15 9M9 21H3M3 21V15M3 21L9 15"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </div>
              </button>
              <div class="similar-image-info">
                <div class="image-header">
                  <div class="image-id">#{similarImage.id}</div>
                  <div
                    class="distance-badge"
                    style="background-color: {getDistanceProps(
                      similarImage.distance,
                      getAllDistances()
                    ).color}; color: white;"
                    title="Cosine distance: {formatDistance(
                      similarImage.distance
                    )} | {getDistanceProps(
                      similarImage.distance,
                      getAllDistances()
                    ).label}"
                  >
                    {formatDistance(similarImage.distance)}
                  </div>
                </div>
                <div
                  class="similarity-label"
                  style="color: {getDistanceProps(
                    similarImage.distance,
                    getAllDistances()
                  ).color}; font-weight: 600;"
                >
                  {getDistanceProps(similarImage.distance, getAllDistances())
                    .label}
                </div>
                <div class="image-question">
                  <strong>Q:</strong>
                  {similarImage.question}
                </div>
                <div class="image-answer">
                  <strong>A:</strong>
                  {similarImage.crowd_majority}
                </div>
              </div>
            </div>
          {/each}
          {#if result.with_context.similar_images.length > 4}
            <div class="more-images">
              +{result.with_context.similar_images.length - 4} more images
            </div>
          {/if}
        </div>
      {:else}
        <div class="no-context">No context images</div>
      {/if}
    </div>
  </td>

  <!-- Response (With Context) -->
  <td class="col-with-context">
    <div class="response-content">
      {#if result.with_context}
        <div class="response-header">
          <span class="context-indicator with-context">With Context</span>
          <div class="header-right">
            <div class="evaluation-buttons">
              <button
                class="eval-btn directly-answered {getEvaluationClass(
                  true,
                  'directly_answered'
                )}"
                onclick={() => setEvaluation(true, "directly_answered")}
                title="✅ Directly Answered (3 points): The model explicitly states the correct answer and directly addresses the question with the expected information."
              >
                ✅
              </button>
              <button
                class="eval-btn inferable {getEvaluationClass(
                  true,
                  'inferable'
                )}"
                onclick={() => setEvaluation(true, "inferable")}
                title="💡 Inferable (2 points): The model provides enough visual detail or context for a human to infer the correct answer, even if not explicitly stated."
              >
                💡
              </button>
              <button
                class="eval-btn missing-incorrect {getEvaluationClass(
                  true,
                  'missing_incorrect'
                )}"
                onclick={() => setEvaluation(true, "missing_incorrect")}
                title="❌ Missing/Incorrect (1 point): The model fails to mention key information or provides incorrect details about the visual content."
              >
                ❌
              </button>
              <button
                class="eval-btn hallucination {getEvaluationClass(
                  true,
                  'hallucination'
                )}"
                onclick={() => setEvaluation(true, "hallucination")}
                title="🤯 Hallucination (0 points): The model mentions things that are not present in the image or provides actively misleading information."
              >
                🤯
              </button>
            </div>
            <div class="processing-time">
              <span class="time-text">
                {formatProcessingTime(result.with_context.processing_time)}
              </span>
              <div class="time-bar-container">
                <div
                  class="time-bar"
                  style="width: {getTimeBarProps(
                    result.with_context.processing_time
                  ).width}%; background-color: {getTimeBarProps(
                    result.with_context.processing_time
                  ).color};"
                ></div>
              </div>
            </div>
          </div>
        </div>
        <div class="keywords-info">
          <span class="keywords-label">Highlighting:</span>
          <span class="keywords-list">
            {#each getHighlightKeywords().slice(0, 6) as keyword}
              <span class="keyword-tag">{keyword}</span>
            {/each}
            {#if getHighlightKeywords().length > 6}
              <span class="keyword-tag more"
                >+{getHighlightKeywords().length - 6}</span
              >
            {/if}
          </span>
        </div>
        {#if result.with_context.error}
          <div class="response-error">
            <strong>Error:</strong>
            {result.with_context.error}
          </div>
        {:else}
          <div class="response-text-container">
            <div class="response-text">
              {@html highlightKeywords(
                getDisplayText(
                  result.with_context.llm_response,
                  isWithContextExpanded
                )
              )}
            </div>
            {#if shouldShowExpandButton(result.with_context.llm_response)}
              <button
                class="expand-text-btn"
                onclick={toggleWithContextExpansion}
                aria-label={isWithContextExpanded
                  ? "Show less text"
                  : "Show more text"}
              >
                {isWithContextExpanded ? "Show less" : "Show more"}
                <svg
                  class="expand-text-icon"
                  class:rotated={isWithContextExpanded}
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6 9L12 15L18 9"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
            {/if}
          </div>
        {/if}
      {:else}
        <div class="no-response">No data with context</div>
      {/if}
    </div>
  </td>

  <!-- Response (Without Context) -->
  <td class="col-without-context">
    <div class="response-content">
      {#if result.without_context}
        <div class="response-header">
          <span class="context-indicator without-context">Without Context</span>
          <div class="header-right">
            <div class="evaluation-buttons">
              <button
                class="eval-btn directly-answered {getEvaluationClass(
                  false,
                  'directly_answered'
                )}"
                onclick={() => setEvaluation(false, "directly_answered")}
                title="✅ Directly Answered (3 points): The model explicitly states the correct answer and directly addresses the question with the expected information."
              >
                ✅
              </button>
              <button
                class="eval-btn inferable {getEvaluationClass(
                  false,
                  'inferable'
                )}"
                onclick={() => setEvaluation(false, "inferable")}
                title="💡 Inferable (2 points): The model provides enough visual detail or context for a human to infer the correct answer, even if not explicitly stated."
              >
                💡
              </button>
              <button
                class="eval-btn missing-incorrect {getEvaluationClass(
                  false,
                  'missing_incorrect'
                )}"
                onclick={() => setEvaluation(false, "missing_incorrect")}
                title="❌ Missing/Incorrect (1 point): The model fails to mention key information or provides incorrect details about the visual content."
              >
                ❌
              </button>
              <button
                class="eval-btn hallucination {getEvaluationClass(
                  false,
                  'hallucination'
                )}"
                onclick={() => setEvaluation(false, "hallucination")}
                title="🤯 Hallucination (0 points): The model mentions things that are not present in the image or provides actively misleading information."
              >
                🤯
              </button>
            </div>
            <div class="processing-time">
              <span class="time-text">
                {formatProcessingTime(result.without_context.processing_time)}
              </span>
              <div class="time-bar-container">
                <div
                  class="time-bar"
                  style="width: {getTimeBarProps(
                    result.without_context.processing_time
                  ).width}%; background-color: {getTimeBarProps(
                    result.without_context.processing_time
                  ).color};"
                ></div>
              </div>
            </div>
          </div>
        </div>
        {#if result.without_context.error}
          <div class="response-error">
            <strong>Error:</strong>
            {result.without_context.error}
          </div>
        {:else}
          <div class="response-text-container">
            <div class="response-text">
              {@html highlightKeywords(
                getDisplayText(
                  result.without_context.llm_response,
                  isWithoutContextExpanded
                )
              )}
            </div>
            {#if shouldShowExpandButton(result.without_context.llm_response)}
              <button
                class="expand-text-btn"
                onclick={toggleWithoutContextExpansion}
                aria-label={isWithoutContextExpanded
                  ? "Show less text"
                  : "Show more text"}
              >
                {isWithoutContextExpanded ? "Show less" : "Show more"}
                <svg
                  class="expand-text-icon"
                  class:rotated={isWithoutContextExpanded}
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6 9L12 15L18 9"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
            {/if}
          </div>
        {/if}
      {:else}
        <div class="no-response">No data without context</div>
      {/if}
    </div>
  </td>

  <!-- Correctness Score -->
  <td class="col-score">
    <div class="score-display">
      <div
        class="score-value"
        style="color: {getScoreColor(getCorrectnessScore())}"
      >
        {formatScore(getCorrectnessScore())}
      </div>
      <div class="score-label">
        {#if getCorrectnessScore() >= 0}
          /3.0
        {:else}
          Not rated
        {/if}
      </div>
    </div>
  </td>

  <!-- Context Impact -->
  <td class="col-context-impact">
    <div class="impact-display">
      <div
        class="impact-score"
        style="color: {getContextImpactColor(contextImpactScore)}"
      >
        {#if contextImpactScore !== null}
          {contextImpactScore > 0 ? "+" : ""}{contextImpactScore}
        {:else}
          -
        {/if}
      </div>
      <div class="impact-label">
        {getContextImpactDescription(contextImpactScore)}
      </div>
    </div>
  </td>
</tr>

<!-- Image Modal -->
<ImageModal
  bind:isOpen={isModalOpen}
  images={modalImages}
  bind:currentIndex={currentImageIndex}
/>

<style>
  .result-row {
    border-bottom: 1px solid #e9ecef;
  }

  .result-row:hover {
    background-color: #f8f9fa;
  }

  .result-row td {
    padding: 1rem 0.75rem;
    vertical-align: top;
    border-right: 1px solid #f1f3f4;
  }

  .result-row td:last-child {
    border-right: none;
  }

  /* Column widths - Fixed layout */
  .col-id {
    width: 80px;
    min-width: 80px;
    max-width: 80px;
    box-sizing: border-box;
  }

  .col-details {
    width: 250px;
    min-width: 250px;
    max-width: 250px;
    box-sizing: border-box;
  }

  .col-context-images {
    width: 300px;
    min-width: 300px;
    max-width: 300px;
    box-sizing: border-box;
  }

  .col-with-context {
    width: 300px;
    min-width: 300px;
    max-width: 300px;
    box-sizing: border-box;
  }

  .col-without-context {
    width: 300px;
    min-width: 300px;
    max-width: 300px;
    box-sizing: border-box;
  }

  .col-score {
    width: 60px;
    min-width: 60px;
    max-width: 60px;
    text-align: center;
    box-sizing: border-box;
  }

  .col-context-impact {
    width: 80px;
    min-width: 80px;
    max-width: 80px;
    text-align: center;
    box-sizing: border-box;
  }

  /* Prevent layout shift and page scrolling */
  .col-id,
  .col-details,
  .col-context-images,
  .col-with-context,
  .col-without-context,
  .col-score,
  .col-context-impact {
    vertical-align: top;
    overflow-wrap: break-word;
    word-wrap: break-word;
    position: relative;
  }

  .expand-text-btn:hover {
    background-color: #e9ecef;
    border-color: #adb5bd;
  }

  .expand-text-btn:focus {
    outline: 2px solid #007bff;
    outline-offset: 2px;
  }

  /* ID Column */
  .id-content {
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: center;
  }

  .validation-id {
    font-family: monospace;
    background: #e9ecef;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    font-size: 0.8rem;
    color: #495057;
  }

  /* Image Container in ID Column */
  .id-content .image-container {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 0;
  }

  .id-content .query-image {
    max-width: 80px;
    max-height: 80px;
    width: auto;
    height: auto;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    object-fit: cover;
    display: block;
  }

  /* Details Column */
  .details-content {
    font-size: 0.85rem;
  }

  .detail-item {
    margin-bottom: 0.75rem;
  }

  .detail-item:last-child {
    margin-bottom: 0;
  }

  .detail-item strong {
    display: block;
    color: #495057;
    margin-bottom: 0.25rem;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .question-text,
  .answer-text {
    margin: 0;
    line-height: 1.4;
    color: #333;
  }

  /* Model info in details */
  .model-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .model-name {
    font-weight: 600;
    color: #333;
    font-size: 0.9rem;
  }

  .embedding-provider {
    font-size: 0.8rem;
    color: #666;
    background: #f8f9fa;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    align-self: flex-start;
  }

  /* Image Column */
  .image-container {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 1rem;
  }

  .image-button {
    position: relative;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    border-radius: 4px;
    overflow: hidden;
    transition:
      transform 0.2s,
      box-shadow 0.2s;
  }

  .image-button:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .query-image {
    max-width: 100px;
    max-height: 100px;
    width: auto;
    height: auto;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    object-fit: cover;
    display: block;
  }

  .clickable-image {
    transition: opacity 0.2s;
  }

  .image-button:hover .clickable-image {
    opacity: 0.8;
  }

  .image-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.2s;
    border-radius: 4px;
  }

  .image-overlay.small {
    background: rgba(0, 0, 0, 0.6);
  }

  .image-button:hover .image-overlay {
    opacity: 1;
  }

  .expand-icon {
    color: white;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.5));
  }

  /* Score Column */
  .score-display {
    text-align: center;
    font-family: monospace;
  }

  .score-value {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1;
  }

  .score-label {
    font-size: 0.7rem;
    color: #666;
    margin-top: 0.1rem;
  }

  /* Context Impact Column */
  .impact-display {
    text-align: center;
    font-family: monospace;
  }

  .impact-score {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1;
  }

  .impact-label {
    font-size: 0.65rem;
    color: #666;
    margin-top: 0.1rem;
    line-height: 1.2;
  }

  /* Context Images */
  .context-images {
    width: 100%;
  }

  .similar-images-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .similar-image-item {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 6px;
    border: 1px solid #e9ecef;
  }

  .context-image-button {
    position: relative;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;
    width: 60px;
    height: 60px;
    transition:
      transform 0.2s,
      box-shadow 0.2s;
  }

  .context-image-button:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .similar-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 3px;
    border: 1px solid #e9ecef;
    display: block;
  }

  .similar-image-info {
    flex: 1;
    font-size: 0.75rem;
    line-height: 1.3;
  }

  .image-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
  }

  .image-id {
    font-weight: 600;
    color: #495057;
    font-family: monospace;
  }

  .distance-badge {
    background-color: #6c757d;
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
    border: 2px solid rgba(255, 255, 255, 0.2);
    font-family: monospace;
    letter-spacing: 0.5px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .similarity-label {
    font-size: 0.7rem;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .image-question,
  .image-answer {
    margin-bottom: 0.25rem;
    color: #333;
  }

  .image-question:last-child,
  .image-answer:last-child {
    margin-bottom: 0;
  }

  .image-question strong,
  .image-answer strong {
    color: #666;
    font-weight: 600;
  }

  .more-images {
    text-align: center;
    font-size: 0.75rem;
    color: #666;
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 3px;
    border: 1px dashed #ddd;
    margin-top: 0.5rem;
  }

  .no-context {
    text-align: center;
    color: #999;
    font-style: italic;
    font-size: 0.8rem;
    padding: 1rem 0;
  }

  /* Response Columns */
  .response-content {
    width: 100%;
  }

  .response-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .evaluation-buttons {
    display: flex;
    gap: 0.2rem;
  }

  .eval-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 3px;
    padding: 0.2rem;
    cursor: pointer;
    font-size: 0.7rem;
    line-height: 1;
    transition: all 0.2s ease;
    opacity: 0.6;
    min-width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .eval-btn:hover {
    opacity: 1;
    transform: scale(1.1);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    z-index: 10;
  }

  .eval-btn:focus {
    outline: 2px solid #007bff;
    outline-offset: 2px;
  }

  .eval-btn.active {
    opacity: 1;
    border-width: 2px;
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .eval-btn.directly-answered.active {
    background: #d4edda;
    border-color: #28a745;
    box-shadow: 0 2px 8px rgba(40, 167, 69, 0.3);
  }

  .eval-btn.inferable.active {
    background: #d1ecf1;
    border-color: #17a2b8;
    box-shadow: 0 2px 8px rgba(23, 162, 184, 0.3);
  }

  .eval-btn.missing-incorrect.active {
    background: #fff3cd;
    border-color: #ffc107;
    box-shadow: 0 2px 8px rgba(255, 193, 7, 0.3);
  }

  .eval-btn.hallucination.active {
    background: #f8d7da;
    border-color: #dc3545;
    box-shadow: 0 2px 8px rgba(220, 53, 69, 0.3);
  }

  .context-indicator {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.2rem 0.5rem;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .context-indicator.with-context {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }

  .context-indicator.without-context {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }

  .processing-time {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.25rem;
    min-width: 80px;
  }

  .time-text {
    font-size: 0.75rem;
    color: #666;
    font-family: monospace;
    white-space: nowrap;
  }

  .time-bar-container {
    width: 60px;
    height: 8px;
    background: #e9ecef;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid #dee2e6;
  }

  .time-bar {
    height: 100%;
    border-radius: 3px;
    transition: all 0.3s ease;
    min-width: 2px;
  }

  .response-text-container {
    position: relative;
  }

  .response-text {
    font-size: 0.85rem;
    line-height: 1.4;
    color: #333;
    word-wrap: break-word;
    white-space: pre-wrap;
    margin-bottom: 0.5rem;
  }

  /* Keyword highlighting */
  :global(.keyword-highlight) {
    background: linear-gradient(120deg, #a2e6fa 0%, #f9f06b 100%);
    background-size: 100% 100%;
    padding: 0.1em 0.2em;
    border-radius: 3px;
    font-weight: 600;
    color: #2c3e50;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    border: 1px solid rgba(0, 0, 0, 0.1);
  }

  .keywords-info {
    background: #f8f9fa;
    padding: 0.5rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border: 1px solid #e9ecef;
  }

  .keywords-label {
    font-size: 0.7rem;
    color: #666;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: block;
    margin-bottom: 0.25rem;
  }

  .keywords-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .keyword-tag {
    background: #e9ecef;
    color: #495057;
    font-size: 0.7rem;
    padding: 0.2rem 0.4rem;
    border-radius: 12px;
    font-family: monospace;
    border: 1px solid #dee2e6;
  }

  .keyword-tag.more {
    background: #6c757d;
    color: white;
    font-weight: 600;
  }

  .expand-text-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 3px;
    padding: 0.2rem 0.4rem;
    font-size: 0.7rem;
    color: #007bff;
    cursor: pointer;
    margin-top: 0.5rem;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    white-space: nowrap;
  }

  .expand-text-btn:hover {
    color: #0056b3;
    text-decoration: underline;
  }

  .expand-text-icon {
    transition: transform 0.2s ease;
  }

  .expand-text-icon.rotated {
    transform: rotate(180deg);
  }

  .response-error {
    font-size: 0.85rem;
    color: #dc3545;
    background: #f8d7da;
    padding: 0.5rem;
    border-radius: 4px;
    border: 1px solid #f5c6cb;
  }

  .no-response {
    text-align: center;
    color: #999;
    font-style: italic;
    font-size: 0.8rem;
    padding: 1rem 0;
  }

  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .result-row td {
      padding: 0.75rem 0.5rem;
    }

    .col-id {
      width: 70px;
      min-width: 70px;
    }

    .col-details {
      width: 200px;
      min-width: 200px;
    }

    .col-context-images {
      width: 280px;
      min-width: 280px;
      max-width: 280px;
    }

    .col-with-context {
      width: 280px;
      min-width: 280px;
      max-width: 280px;
    }

    .col-without-context {
      width: 280px;
      min-width: 280px;
      max-width: 280px;
    }

    .col-score {
      width: 50px;
      min-width: 50px;
    }

    .col-context-impact {
      width: 70px;
      min-width: 70px;
    }

    .id-content .query-image {
      max-width: 60px;
      max-height: 60px;
    }

    .query-image {
      max-width: 60px;
      max-height: 60px;
    }

    .similar-image-item {
      padding: 0.375rem;
      gap: 0.375rem;
    }

    .context-image-button {
      width: 50px;
      height: 50px;
    }

    .similar-image-info {
      font-size: 0.7rem;
    }

    .image-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }

    .image-id {
      font-size: 0.7rem;
    }

    .distance-badge {
      padding: 0.15rem 0.4rem;
      font-size: 0.65rem;
      font-weight: 600;
    }

    .similarity-label {
      font-size: 0.65rem;
    }

    .image-question,
    .image-answer {
      font-size: 0.7rem;
    }

    .expand-icon {
      width: 14px;
      height: 14px;
    }

    .details-content,
    .response-text {
      font-size: 0.8rem;
    }

    .expand-text-btn {
      font-size: 0.75rem;
    }

    .model-name {
      font-size: 0.8rem;
    }

    .embedding-provider {
      font-size: 0.7rem;
    }

    .score-value {
      font-size: 1rem;
    }

    .score-label {
      font-size: 0.65rem;
    }

    .impact-score {
      font-size: 1rem;
    }

    .impact-label {
      font-size: 0.6rem;
    }

    .keywords-info {
      padding: 0.375rem;
    }

    .keywords-label {
      font-size: 0.65rem;
    }

    .keyword-tag {
      font-size: 0.65rem;
      padding: 0.15rem 0.3rem;
    }

    .processing-time {
      min-width: 70px;
    }

    .time-text {
      font-size: 0.7rem;
    }

    .time-bar-container {
      width: 50px;
      height: 6px;
    }

    .header-right {
      gap: 0.5rem;
    }

    .evaluation-buttons {
      gap: 0.2rem;
    }

    .eval-btn {
      min-width: 22px;
      height: 22px;
      padding: 0.15rem;
      font-size: 0.65rem;
    }
  }
</style>
