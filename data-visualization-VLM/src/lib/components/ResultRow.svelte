<script lang="ts">
  import ImageModal from "./ImageModal.svelte";

  // ============================================================================
  // TYPES & INTERFACES
  // ============================================================================
  
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

  type EvaluationType =
    | "directly_answered"
    | "inferable"
    | "missing_incorrect"
    | "hallucination"
    | null;

  // ============================================================================
  // PROPS
  // ============================================================================
  
  let {
    result,
    allResults,
    fullDataset = null,
    columnVisibility = {
      id: true,
      contextImages: true,
      withContext: true,
      withoutContext: true,
      score: true,
      contextImpact: true
    },
    rowNumber
  }: { 
    result: GroupedResult; 
    allResults: GroupedResult[];
    fullDataset?: GroupedResult[] | null;
    columnVisibility?: {
      id: boolean;
      contextImages: boolean;
      withContext: boolean;
      withoutContext: boolean;
      score: boolean;
      contextImpact: boolean;
    };
    rowNumber: number;
  } = $props();

  // ============================================================================
  // STATE MANAGEMENT
  // ============================================================================
  
  // Modal state
  let isModalOpen = $state(false);
  let modalImages: ImageData[] = $state([]);
  let currentImageIndex = $state(0);

  // Text expansion state
  let isWithContextExpanded = $state(true);
  let isWithoutContextExpanded = $state(true);

  // Storage update trigger for reactivity
  let storageUpdateTrigger = $state(0);

  // Listen for storage changes
  if (typeof window !== "undefined") {
    window.addEventListener("storage", () => storageUpdateTrigger++);
    window.addEventListener("evaluationsCleared", () => storageUpdateTrigger++);
  }

  // ============================================================================
  // EVALUATION FUNCTIONS
  // ============================================================================
  
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

  function saveEvaluations(evaluations: Record<string, EvaluationType>) {
    if (typeof window === "undefined") return;
    try {
      sessionStorage.setItem("llm-evaluations", JSON.stringify(evaluations));
    } catch (e) {
      console.warn("Failed to save evaluations");
    }
  }

  function getResponseKey(withContext: boolean): string {
    return `${result.validation_id}-${result.model_name}-${result.embedding_provider}-${withContext ? "with" : "without"}`;
  }

  function setEvaluation(withContext: boolean, evaluation: EvaluationType) {
    const evaluations = getStoredEvaluations();
    const key = getResponseKey(withContext);

    if (evaluations[key] === evaluation) {
      delete evaluations[key];
    } else {
      evaluations[key] = evaluation;
    }

    saveEvaluations(evaluations);
    storageUpdateTrigger++;

    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("evaluationChanged"));
    }
  }

  function getEvaluation(withContext: boolean): EvaluationType {
    storageUpdateTrigger; // Trigger reactivity
    const evaluations = getStoredEvaluations();
    const key = getResponseKey(withContext);
    return evaluations[key] || null;
  }

  function getEvaluationClass(withContext: boolean, type: EvaluationType): string {
    return getEvaluation(withContext) === type ? "active" : "";
  }

  function getNumericScore(evaluation: EvaluationType): number {
    switch (evaluation) {
      case "directly_answered": return 3;
      case "inferable": return 2;
      case "missing_incorrect": return 1;
      case "hallucination": return 0;
      default: return -1;
    }
  }

  // ============================================================================
  // SCORING FUNCTIONS
  // ============================================================================
  
  function getCorrectnessScore(): number {
    const withScore = getNumericScore(getEvaluation(true));
    const withoutScore = getNumericScore(getEvaluation(false));
    
    const totalScore = withScore + withoutScore;
    const evaluatedCount = (withScore >= 0 ? 1 : 0) + (withoutScore >= 0 ? 1 : 0);
    
    if (evaluatedCount === 0) return -1;
    return totalScore / evaluatedCount;
  }

  function getContextImpactScore(): number | null {
    const withScore = getNumericScore(getEvaluation(true));
    const withoutScore = getNumericScore(getEvaluation(false));
    
    if (withScore < 0 || withoutScore < 0) return null;
    return withScore - withoutScore;
  }

  function getContextImpactDescription(score: number | null): string {
    if (score === null) return "Not evaluated";
    if (score === 3) return "Major Improvement";
    if (score === 2) return "Significant Improvement";
    if (score === 1) return "Minor Improvement";
    if (score === 0) return "No Change";
    if (score === -1) return "Minor Degradation";
    if (score === -2) return "Major Degradation";
    if (score === -3) return "Catastrophic Failure";
    return score > 0 ? "Improvement" : "Degradation";
  }

  function getContextImpactColor(score: number | null): string {
    if (score === null) return "#999";
    if (score >= 2) return "#28a745";
    if (score === 1) return "#17a2b8";
    if (score === 0) return "#6c757d";
    if (score === -1) return "#ffc107";
    if (score <= -2) return "#dc3545";
    return "#6c757d";
  }

  function formatScore(score: number): string {
    return score < 0 ? "-" : score.toFixed(1);
  }

  function getScoreColor(score: number): string {
    if (score < 0) return "#999";
    if (score >= 2.5) return "#28a745";
    if (score >= 2.0) return "#17a2b8";
    if (score >= 1.0) return "#ffc107";
    return "#dc3545";
  }

  // Reactive context impact score
  let contextImpactScore = $derived(getContextImpactScore());

  // ============================================================================
  // TEXT PROCESSING FUNCTIONS
  // ============================================================================
  
  function shouldShowExpandButton(text: string, maxLength: number = 150): boolean {
    return typeof text === "string" && text.length > maxLength;
  }

  function getDisplayText(text: string, isExpanded: boolean, maxLength: number = 150): string {
    if (!text) return "";
    if (isExpanded || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  }

  function toggleWithContextExpansion() {
    const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;
    isWithContextExpanded = !isWithContextExpanded;
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        window.scrollTo({ top: currentScrollY, behavior: "instant" });
      });
    }
  }

  function toggleWithoutContextExpansion() {
    const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;
    isWithoutContextExpanded = !isWithoutContextExpanded;
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        window.scrollTo({ top: currentScrollY, behavior: "instant" });
      });
    }
  }

  // ============================================================================
  // KEYWORD HIGHLIGHTING FUNCTIONS
  // ============================================================================
  
  function extractKeywords(text: string): string[] {
    if (!text) return [];

    const stopWords = new Set([
      "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", 
      "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", 
      "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", 
      "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", 
      "me", "him", "her", "us", "them", "my", "your", "his", "her", "its", "our", 
      "their", "what", "where", "when", "why", "how", "who", "which"
    ]);

    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, " ")
      .split(/\s+/)
      .filter((word) => word.length > 2 && !stopWords.has(word))
      .slice(0, 10);
  }

  function getHighlightKeywords(): string[] {
    return extractKeywords(result.crowd_majority);
  }

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

  // ============================================================================
  // MODAL FUNCTIONS
  // ============================================================================
  
  function openQueryImageModal() {
    modalImages = [{
      url: result.image_url,
      alt: `Query image for validation ${result.validation_id}`,
      title: `Query Image - ${result.real_question}`,
    }];
    currentImageIndex = 0;
    isModalOpen = true;
  }

  function openContextImageModal(imageUrl: string, index: number) {
    if (result.with_context?.similar_images) {
      modalImages = result.with_context.similar_images.map((img, i) => ({
        url: img.image_url,
        alt: `Context image ${i + 1}`,
        title: `Context Image ${i + 1} of ${result.with_context!.similar_images.length}`,
      }));
      currentImageIndex = index;
      isModalOpen = true;
    }
  }

  // ============================================================================
  // DISTANCE & SIMILARITY FUNCTIONS
  // ============================================================================
  
  function getDistanceProps(distance: number, allDistances: number[]) {
    if (allDistances.length === 0) {
      return { color: "#6c757d", label: "Unknown", rawDistance: distance };
    }

    let color: string;
    let label: string;

    if (distance <= 0.2) {
      color = "#28a745";
      label = "Very Similar";
    } else if (distance <= 0.5) {
      color = "#007bff";
      label = "Similar";
    } else if (distance <= 1.0) {
      color = "#fd7e14";
      label = "Moderate Similarity";
    } else {
      color = "#dc3545";
      label = "Poor Similarity";
    }

    return { color, label, rawDistance: distance };
  }

  function getAllDistances(): number[] {
    if (!result.with_context?.similar_images) return [];
    return result.with_context.similar_images.map((img) => img.distance);
  }

  function formatDistance(distance: number): string {
    return distance.toFixed(3);
  }

  // ============================================================================
  // LENGTH ANALYSIS FUNCTIONS
  // ============================================================================
  
  function getLengthStats(withContext: boolean): {
    min: number;
    max: number;
    average: number;
    quartiles: number[];
  } {
    // Use fullDataset if available for consistent thermometer baseline across all filters,
    // otherwise fall back to allResults (filtered data) for backward compatibility
    const datasetToUse = fullDataset || allResults;
    
    const contextSpecificLengths: number[] = [];
    const allLengths: number[] = [];
    
    datasetToUse.forEach((res) => {
      const contextResponse = withContext ? res.with_context?.llm_response : res.without_context?.llm_response;
      if (contextResponse) {
        const wordCount = contextResponse.trim().split(/\s+/).length;
        contextSpecificLengths.push(wordCount);
        allLengths.push(wordCount);
      }
      
      const otherContextResponse = withContext ? res.without_context?.llm_response : res.with_context?.llm_response;
      if (otherContextResponse) {
        const wordCount = otherContextResponse.trim().split(/\s+/).length;
        allLengths.push(wordCount);
      }
    });
    
    if (allLengths.length === 0) return { min: 0, max: 100, average: 50, quartiles: [0, 25, 50, 75, 100] };
    
    const globalMin = Math.min(...allLengths);
    const globalMax = Math.max(...allLengths);
    const contextAverage = contextSpecificLengths.length > 0 
      ? contextSpecificLengths.reduce((sum, len) => sum + len, 0) / contextSpecificLengths.length
      : (globalMin + globalMax) / 2;
    
    const range = globalMax - globalMin;
    const quartiles = [
      globalMin,
      globalMin + range * 0.25,
      globalMin + range * 0.5,
      globalMin + range * 0.75,
      globalMax
    ];
    
    return { min: globalMin, max: globalMax, average: contextAverage, quartiles };
  }

  function getThermometerData(wordCount: number, withContext: boolean): {
    percentage: number;
    color: string;
    stats: { min: number; max: number; average: number; quartiles: number[] };
  } {
    const stats = getLengthStats(withContext);
    const range = stats.max - stats.min;
    const normalizedValue = range > 0 ? (wordCount - stats.min) / range : 0.5;
    const percentage = Math.min(100, Math.max(5, normalizedValue * 100));
    
    let color: string;
    
    if (range === 0) {
      color = '#ffc107';
    } else if (normalizedValue <= 0.33) {
      const localRatio = normalizedValue / 0.33;
      const r = Math.round(40 + (255 - 40) * localRatio);
      const g = Math.round(167 + (193 - 167) * localRatio);
      const b = Math.round(69 + (7 - 69) * localRatio);
      color = `rgb(${r}, ${g}, ${b})`;
    } else if (normalizedValue <= 0.66) {
      const localRatio = (normalizedValue - 0.33) / 0.33;
      const r = 255;
      const g = Math.round(193 + (165 - 193) * localRatio);
      const b = 7;
      color = `rgb(${r}, ${g}, ${b})`;
    } else {
      const localRatio = (normalizedValue - 0.66) / 0.34;
      const r = Math.round(255 + (220 - 255) * localRatio);
      const g = Math.round(165 + (53 - 165) * localRatio);
      const b = Math.round(0 + (69 - 0) * localRatio);
      color = `rgb(${r}, ${g}, ${b})`;
    }
    
    return { percentage, color, stats };
  }

  function getConcisenessMeter(response: string): {
    wordCount: number;
    penalty: number;
    level: string;
    color: string;
    description: string;
  } {
    if (!response) {
      return {
        wordCount: 0,
        penalty: 0,
        level: "N/A",
        color: "#6c757d",
        description: "No response",
      };
    }

    const wordCount = response.trim().split(/\s+/).length;
    
    // Calculate penalty
    let penalty = 0;
    if (wordCount >= 10 && wordCount <= 50) {
      penalty = 0;
    } else if (wordCount < 10) {
      penalty = 0.1;
    } else if (wordCount <= 100) {
      penalty = 0.2;
    } else if (wordCount <= 150) {
      penalty = 0.4;
    } else {
      penalty = 0.6;
    }

    if (wordCount >= 10 && wordCount <= 50) {
      return { wordCount, penalty, level: "Ideal", color: "#28a745", description: "Perfect length" };
    } else if (wordCount < 10) {
      return { wordCount, penalty, level: "Brief", color: "#ffc107", description: "May lack detail" };
    } else if (wordCount <= 100) {
      return { wordCount, penalty, level: "Verbose", color: "#fd7e14", description: "Moderately long" };
    } else if (wordCount <= 150) {
      return { wordCount, penalty, level: "Long", color: "#dc3545", description: "Quite verbose" };
    } else {
      return { wordCount, penalty, level: "Excessive", color: "#6f42c1", description: "Too verbose" };
    }
  }
</script>

<tr class="result-row">
  <!-- ID with Query Image and Details -->
  {#if columnVisibility.id}
    <td class="col-id">
      <div class="id-content">
        <div class="id-header">
          <span class="validation-id">ID #{result.validation_id}</span>
          <span class="validation-id">Row {rowNumber}</span>
        </div>
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
                width="40"
                height="80"
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
      </div>
    </td>
  {/if}



  <!-- Context Images -->
  {#if columnVisibility.contextImages}
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
  {/if}

  <!-- Response (With Context) -->
  {#if columnVisibility.withContext}
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

        <!-- Length Thermometer -->
        {@const concisenessMeter = getConcisenessMeter(
          result.with_context.llm_response
        )}
        {@const thermometerData = getThermometerData(
          concisenessMeter.wordCount,
          true
        )}
        {@const range = thermometerData.stats.max - thermometerData.stats.min}
        {@const avgPercentage = range > 0 ? Math.min(100, ((thermometerData.stats.average - thermometerData.stats.min) / range) * 100) : 50}
        <div class="conciseness-info">
          <div class="thermometer-section">
            <div class="conciseness-label">
              <span class="word-count">{concisenessMeter.wordCount} words</span>
            </div>
            <div class="length-thermometer">
              <div class="thermometer-bar thermometer-tooltip-trigger">
                <div 
                  class="thermometer-fill"
                  style="width: {thermometerData.percentage}%; background-color: {thermometerData.color}"
                ></div>
                
                <!-- Custom tooltip -->
                <div class="thermometer-tooltip">
                  <div class="tooltip-line"><strong>Length:</strong> {concisenessMeter.wordCount} words</div>
                  <div class="tooltip-line"><strong>Position:</strong> {Math.round(thermometerData.percentage)}%</div>
                </div>
                
                <!-- Quartile markings -->
                <div class="thermometer-markings">
                  <div class="marking" style="left: 0%"></div>
                  <div class="marking" style="left: 25%"></div>
                  <div class="marking" style="left: 50%"></div>
                  <div class="marking" style="left: 75%"></div>
                  <div class="marking" style="left: 100%"></div>
                </div>
                
                <!-- Average marker -->
                <div 
                  class="average-marker" 
                  style="left: {avgPercentage}%"
                  title="Average: {Math.round(thermometerData.stats.average)} words"
                ></div>
                
                <!-- Current value indicator -->
                <div 
                  class="current-value-indicator" 
                  style="left: {thermometerData.percentage}%"
                  title="Current: {concisenessMeter.wordCount} words"
                ></div>
              </div>
              
              <!-- Thermometer Labels -->
              <div class="thermometer-labels">
                <div class="label-container">
                  <div class="label min-label" style="left: 0%">
                    <span class="label-value">{Math.round(thermometerData.stats.min)}</span>
                    <span class="label-text">min</span>
                  </div>
                  <div class="label avg-label" style="left: {avgPercentage}%">
                    <span class="label-value">{Math.round(thermometerData.stats.average)}</span>
                    <span class="label-text">avg</span>
                  </div>
                  <div class="label max-label" style="left: 100%">
                    <span class="label-value">{Math.round(thermometerData.stats.max)}</span>
                    <span class="label-text">max</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {#if result.with_context.error}
          <div class="response-error">
            <strong>Error:</strong>
            {result.with_context.error}
          </div>
        {:else}
          <div class="response-text-container">
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
            <div class="response-text">
              {@html highlightKeywords(
                getDisplayText(
                  result.with_context.llm_response,
                  isWithContextExpanded
                )
              )}
            </div>
          </div>
        {/if}
      {:else}
        <div class="no-response">No data with context</div>
      {/if}
    </div>
  </td>
  {/if}

  <!-- Response (Without Context) -->
  {#if columnVisibility.withoutContext}
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

        <!-- Length Thermometer -->
        {@const concisenessMeter = getConcisenessMeter(
          result.without_context.llm_response
        )}
        {@const thermometerData = getThermometerData(
          concisenessMeter.wordCount,
          false
        )}
        {@const range = thermometerData.stats.max - thermometerData.stats.min}
        {@const avgPercentage = range > 0 ? Math.min(100, ((thermometerData.stats.average - thermometerData.stats.min) / range) * 100) : 50}
        <div class="conciseness-info">
          <div class="thermometer-section">
           
              <div class="conciseness-label">
                <span class="word-count">{concisenessMeter.wordCount} words</span>
              </div>
       
            
            <div class="length-thermometer">
              <div class="thermometer-bar thermometer-tooltip-trigger">
                <div 
                  class="thermometer-fill"
                  style="width: {thermometerData.percentage}%; background-color: {thermometerData.color}"
                ></div>
                
                <!-- Custom tooltip -->
                <div class="thermometer-tooltip">
                  <div class="tooltip-line"><strong>Length:</strong> {concisenessMeter.wordCount} words</div>
                  <div class="tooltip-line"><strong>Position:</strong> {Math.round(thermometerData.percentage)}%</div>
                </div>
                
                <!-- Quartile markings -->
                <div class="thermometer-markings">
                  <div class="marking" style="left: 0%"></div>
                  <div class="marking" style="left: 25%"></div>
                  <div class="marking" style="left: 50%"></div>
                  <div class="marking" style="left: 75%"></div>
                  <div class="marking" style="left: 100%"></div>
                </div>
                
                <!-- Average marker -->
                <div 
                  class="average-marker" 
                  style="left: {avgPercentage}%"
                  title="Average: {Math.round(thermometerData.stats.average)} words"
                ></div>
                
                
              </div>
              
              <!-- Thermometer Labels -->
              <div class="thermometer-labels">
                <div class="label-container">
                  <div class="label min-label" style="left: 0%">
                    <span class="label-value">{Math.round(thermometerData.stats.min)}</span>
                    <span class="label-text">min</span>
                  </div>
                  <div class="label avg-label" style="left: {avgPercentage}%">
                    <span class="label-value">{Math.round(thermometerData.stats.average)}</span>
                    <span class="label-text">avg</span>
                  </div>
                  <div class="label max-label" style="left: 100%">
                    <span class="label-value">{Math.round(thermometerData.stats.max)}</span>
                    <span class="label-text">max</span>
                  </div>
                </div>
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
            <div class="response-text">
              {@html highlightKeywords(
                getDisplayText(
                  result.without_context.llm_response,
                  isWithoutContextExpanded
                )
              )}
            </div>
          </div>
        {/if}
      {:else}
        <div class="no-response">No data without context</div>
      {/if}
    </div>
  </td>
  {/if}

  <!-- Correctness Score -->
  {#if columnVisibility.score}
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
  {/if}

  <!-- Context Impact -->
  {#if columnVisibility.contextImpact}
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
  {/if}
</tr>

<!-- Image Modal -->
<ImageModal
  bind:isOpen={isModalOpen}
  images={modalImages}
  bind:currentIndex={currentImageIndex}
/>

<style>
  /* ============================================================================
   * BASE ROW LAYOUT
   * ============================================================================ */
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

  /* ============================================================================
   * COLUMN WIDTHS & LAYOUT
   * ============================================================================ */
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
    hyphens: auto;
    white-space: normal;
    overflow: hidden;
    position: relative;
    max-width: 0; /* Forces cells to respect percentage widths */
    box-sizing: border-box;
  }

  .col-id {
    width: 10%;
    min-width: 120px;
  }

  .col-details {
    width: 15%;
    min-width: 180px;
  }

  .col-context-images {
    width: 20%;
    min-width: 220px;
  }

  .col-with-context,
  .col-without-context {
    width: 22%;
    min-width: 230px;
  }

  .col-score {
    width: 6%;
    min-width: 50px;
    text-align: center;
  }

  .col-context-impact {
    width: 8%;
    min-width: 70px;
    text-align: center;
  }

  /* ============================================================================
   * ID COLUMN CONTENT
   * ============================================================================ */
  .id-content {
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .id-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
  }

  .validation-id {
    font-family: monospace;
    background: #e9ecef;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    font-size: 0.8rem;
    color: #495057;
    flex-shrink: 0;
  }

  .id-header .image-container {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    margin: 0;
    width: 100%;
  }

  .id-header .image-button {
    width: 100%;
  }

  .id-content .query-image {
    width: 100%;
    max-width: none;
    height: auto;
    max-height: 150px;
  }

  .id-content .details-content {
    width: 100%;
    font-size: 0.85rem;
  }

  /* ============================================================================
   * DETAILS CONTENT
   * ============================================================================ */
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
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
  }

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

  /* ============================================================================
   * IMAGE COMPONENTS
   * ============================================================================ */
  .image-container {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 1rem;
  }

  .image-button,
  .context-image-button {
    position: relative;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    border-radius: 4px;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
  }

  .image-button:hover,
  .context-image-button:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .context-image-button {
    border-radius: 3px;
    flex-shrink: 0;
    width: 60px;
    height: 60px;
  }

  .context-image-button:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
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

  .similar-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 3px;
    border: 1px solid #e9ecef;
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

  /* ============================================================================
   * CONTEXT IMAGES
   * ============================================================================ */
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

  .no-context,
  .no-response {
    text-align: center;
    color: #999;
    font-style: italic;
    font-size: 0.8rem;
    padding: 1rem 0;
  }

  /* ============================================================================
   * RESPONSE COLUMNS
   * ============================================================================ */
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

  /* ============================================================================
   * EVALUATION BUTTONS
   * ============================================================================ */
  .evaluation-buttons {
    display: flex;
    gap: 0.2rem;
  }

  .eval-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 0.4rem;
    cursor: pointer;
    font-size: 0.9rem;
    line-height: 1;
    transition: all 0.2s ease;
    opacity: 0.6;
    min-width: 32px;
    height: 32px;
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

  /* ============================================================================
   * TEXT CONTENT & EXPANSION
   * ============================================================================ */
  .response-text-container {
    position: relative;
  }

  .response-text {
    font-size: 0.85rem;
    line-height: 1.4;
    color: #333;
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    white-space: pre-wrap;
    margin-bottom: 0.5rem;
    max-width: 100%;
    overflow: hidden;
  }

  .expand-text-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 3px;
    padding: 0.2rem 0.4rem;
    font-size: 0.7rem;
    color: #007bff;
    cursor: pointer;
    margin-bottom: 0.5rem;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    white-space: nowrap;
  }

  .expand-text-btn:hover {
    background-color: #e9ecef;
    border-color: #adb5bd;
    color: #0056b3;
    text-decoration: underline;
  }

  .expand-text-btn:focus {
    outline: 2px solid #007bff;
    outline-offset: 2px;
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

  /* ============================================================================
   * KEYWORD HIGHLIGHTING
   * ============================================================================ */
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

  /* ============================================================================
   * SCORE & IMPACT COLUMNS
   * ============================================================================ */
  .score-display,
  .impact-display {
    text-align: center;
    font-family: monospace;
  }

  .score-value,
  .impact-score {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1;
  }

  .score-label {
    font-size: 0.7rem;
    color: #666;
    margin-top: 0.1rem;
  }

  .impact-label {
    font-size: 0.65rem;
    color: #666;
    margin-top: 0.1rem;
    line-height: 1.2;
  }

  /* ============================================================================
   * CONCISENESS & THERMOMETER
   * ============================================================================ */
  .conciseness-info {
    background: #f8f9fa;
    padding: 0.5rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border: 1px solid #e9ecef;
    min-height: 60px;
    overflow: visible;
  }

  .thermometer-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    --thermometer-margin: 8px;
  }

  .conciseness-label {
    font-size: 0.7rem;
    color: #666;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .word-count {
    font-size: 0.7rem;
    color: #666;
    font-family: monospace;
  }

  .length-thermometer {
    width: 100%;
    min-width: 120px;
    display: flex;
    flex-direction: column;
  }

  .thermometer-bar {
    height: 12px;
    background: #e9ecef;
    border-radius: 6px;
    border: 1px solid #dee2e6;
    overflow: visible;
    position: relative;
    cursor: help;
    margin: 0 var(--thermometer-margin);
    min-width: calc(60px - 2 * var(--thermometer-margin));
  }

  .thermometer-tooltip-trigger {
    position: relative;
  }

  .thermometer-tooltip {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    margin-bottom: 8px;
    background: rgba(0, 0, 0, 0.9);
    color: white;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    white-space: nowrap;
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.1s ease, visibility 0.1s ease;
    pointer-events: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .thermometer-tooltip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: rgba(0, 0, 0, 0.9);
  }

  .thermometer-tooltip-trigger:hover .thermometer-tooltip {
    opacity: 1;
    visibility: visible;
  }

  .tooltip-line {
    margin: 2px 0;
    line-height: 1.3;
  }

  .tooltip-line strong {
    color: #ffc107;
    margin-right: 4px;
  }

  .thermometer-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.3s ease, background-color 0.3s ease;
    background-color: #28a745;
    min-width: 2px;
  }

  .thermometer-markings {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
  }

  .marking {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 1px;
    background: #495057;
    transform: translateX(-0.5px);
  }

  .average-marker {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    background: #007bff;
    transform: translateX(-1px);
    border-radius: 1px;
    box-shadow: 0 0 3px rgba(0, 123, 255, 0.5);
  }

  .current-value-indicator {
    position: absolute;
    top: -8px;
    left: 0;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #dc3545;
    transform: translateX(-4px);
    z-index: 10;
  }

  .thermometer-labels {
    margin-top: 4px;
    height: 32px;
    position: relative;
    margin-left: var(--thermometer-margin);
    margin-right: var(--thermometer-margin);
  }

  .label-container {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .label {
    position: absolute;
    top: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: monospace;
    z-index: 5;
  }

  .min-label {
    transform: translateX(0%);
  }

  .avg-label {
    transform: translateX(-50%);
  }

  .max-label {
    transform: translateX(-100%);
  }

  .label-value {
    font-size: 0.65rem;
    color: #495057;
    font-weight: 600;
    line-height: 1.1;
    text-align: center;
  }

  .label-text {
    font-size: 0.55rem;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    line-height: 1;
    margin-top: 1px;
    text-align: center;
  }

  .avg-label .label-value {
    color: #007bff;
    font-weight: 700;
  }

  .avg-label .label-text {
    color: #007bff;
  }

  /* ============================================================================
   * RESPONSIVE DESIGN
   * ============================================================================ */
  @media (max-width: 1400px) {
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
    .thermometer-section {
      --thermometer-margin: 6px;
    }
    
    .length-thermometer {
      min-width: 100px;
    }
    
    .label-value {
      font-size: 0.6rem;
    }

    .label-text {
      font-size: 0.5rem;
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
    .result-row td {
      padding: 0.75rem 0.5rem;
    }

    .thermometer-section {
      --thermometer-margin: 4px;
    }
    
    .length-thermometer {
      min-width: 80px;
    }
    
    .thermometer-bar {
      height: 10px;
    }
    
    .thermometer-labels {
      height: 28px;
    }

    .label-value {
      font-size: 0.55rem;
    }

    .label-text {
      font-size: 0.45rem;
    }

    .col-id {
      min-width: 160px;
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

    .id-content .query-image {
      width: 100%;
      max-width: none;
      height: auto;
      max-height: 200px;
      border-radius: 4px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      object-fit: cover;
      display: block;
    }

    .query-image {
      width: 100%;
      max-width: none;
      height: auto;
      max-height: 150px;
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

    .score-value,
    .impact-score {
      font-size: 1rem;
    }

    .score-label {
      font-size: 0.65rem;
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

  @media (max-width: 480px) {
    .thermometer-section {
      --thermometer-margin: 2px;
    }
    
    .length-thermometer {
      min-width: 60px;
    }
    
    .thermometer-bar {
      height: 8px;
    }
    
    .thermometer-labels {
      height: 24px;
    }

    .label-value {
      font-size: 0.5rem;
    }

    .label-text {
      font-size: 0.4rem;
    }
    
    .conciseness-info {
      min-height: 50px;
    }
  }
</style>
