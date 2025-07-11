<script lang="ts">
  interface ImageData {
    url: string;
    alt: string;
    title?: string;
  }

  // Props
  let {
    isOpen = $bindable(false),
    images = [],
    currentIndex = $bindable(0),
  }: {
    isOpen: boolean;
    images: ImageData[];
    currentIndex: number;
  } = $props();

  // Handle keyboard events
  function handleKeydown(event: KeyboardEvent) {
    if (!isOpen) return;

    switch (event.key) {
      case "Escape":
        isOpen = false;
        break;
      case "ArrowLeft":
        if (images.length > 1) {
          currentIndex =
            currentIndex > 0 ? currentIndex - 1 : images.length - 1;
        }
        break;
      case "ArrowRight":
        if (images.length > 1) {
          currentIndex =
            currentIndex < images.length - 1 ? currentIndex + 1 : 0;
        }
        break;
    }
  }

  // Handle background click to close
  function handleBackgroundClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      isOpen = false;
    }
  }

  // Navigation functions
  function goToPrevious() {
    if (images.length > 1) {
      currentIndex = currentIndex > 0 ? currentIndex - 1 : images.length - 1;
    }
  }

  function goToNext() {
    if (images.length > 1) {
      currentIndex = currentIndex < images.length - 1 ? currentIndex + 1 : 0;
    }
  }

  // Get current image data
  function getCurrentImage() {
    return images[currentIndex] || null;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen && getCurrentImage()}
  {@const currentImage = getCurrentImage()}
  <div
    class="modal-overlay"
    onclick={handleBackgroundClick}
    role="dialog"
    aria-modal="true"
    aria-label="Image viewer"
  >
    <div class="modal-content">
      <!-- Close button -->
      <button
        class="close-btn"
        onclick={() => (isOpen = false)}
        aria-label="Close image viewer"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M18 6L6 18M6 6L18 18"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>

      <!-- Image container -->
      <div class="image-container">
        <img
          src={currentImage.url}
          alt={currentImage.alt}
          class="modal-image"
        />
      </div>

      <!-- Navigation arrows (only show if multiple images) -->
      {#if images.length > 1}
        <button
          class="nav-btn prev-btn"
          onclick={goToPrevious}
          aria-label="Previous image"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M15 18L9 12L15 6"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>

        <button
          class="nav-btn next-btn"
          onclick={goToNext}
          aria-label="Next image"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M9 18L15 12L9 6"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      {/if}

      <!-- Image info -->
      <div class="image-info">
        {#if currentImage.title}
          <h3 class="image-title">{currentImage.title}</h3>
        {/if}
        {#if images.length > 1}
          <div class="image-counter">
            {currentIndex + 1} of {images.length}
          </div>
        {/if}
      </div>

      <!-- Thumbnail navigation (only show if multiple images) -->
      {#if images.length > 1 && images.length <= 10}
        <div class="thumbnails">
          {#each images as image, index}
            <button
              class="thumbnail"
              class:active={index === currentIndex}
              onclick={() => (currentIndex = index)}
              aria-label="Go to image {index + 1}"
            >
              <img src={image.url} alt="" />
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(4px);
  }

  .modal-content {
    position: relative;
    max-width: 95vw;
    max-height: 95vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .close-btn {
    position: absolute;
    top: -50px;
    right: 0;
    background: rgba(255, 255, 255, 0.1);
    border: none;
    color: white;
    padding: 0.5rem;
    border-radius: 50%;
    cursor: pointer;
    z-index: 1001;
    transition: background-color 0.2s;
    backdrop-filter: blur(8px);
  }

  .close-btn:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  .image-container {
    position: relative;
    max-width: 90vw;
    max-height: 80vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 8px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  }

  .nav-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(255, 255, 255, 0.1);
    border: none;
    color: white;
    padding: 1rem;
    border-radius: 50%;
    cursor: pointer;
    z-index: 1001;
    transition: all 0.2s;
    backdrop-filter: blur(8px);
  }

  .nav-btn:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-50%) scale(1.1);
  }

  .prev-btn {
    left: -60px;
  }

  .next-btn {
    right: -60px;
  }

  .image-info {
    margin-top: 1rem;
    text-align: center;
    color: white;
  }

  .image-title {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
    font-weight: 500;
  }

  .image-counter {
    font-size: 0.9rem;
    opacity: 0.8;
  }

  .thumbnails {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 90vw;
    overflow-x: auto;
    padding: 0.5rem;
  }

  .thumbnail {
    width: 60px;
    height: 45px;
    border: 2px solid transparent;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s;
    background: none;
    padding: 0;
  }

  .thumbnail:hover {
    border-color: rgba(255, 255, 255, 0.5);
    transform: scale(1.05);
  }

  .thumbnail.active {
    border-color: #007bff;
    transform: scale(1.1);
  }

  .thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  /* Mobile responsiveness */
  @media (max-width: 768px) {
    .modal-content {
      max-width: 98vw;
      max-height: 98vh;
    }

    .close-btn {
      top: -40px;
      right: 10px;
    }

    .nav-btn {
      padding: 0.75rem;
    }

    .prev-btn {
      left: -50px;
    }

    .next-btn {
      right: -50px;
    }

    .image-container {
      max-width: 95vw;
      max-height: 75vh;
    }

    .thumbnails {
      max-width: 95vw;
    }

    .thumbnail {
      width: 50px;
      height: 38px;
    }
  }

  @media (max-width: 480px) {
    .nav-btn {
      padding: 0.5rem;
      position: fixed;
      bottom: 100px;
    }

    .prev-btn {
      left: 20px;
    }

    .next-btn {
      right: 20px;
    }

    .close-btn {
      position: fixed;
      top: 20px;
      right: 20px;
    }
  }
</style>
