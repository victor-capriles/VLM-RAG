import os
import json
from typing import Dict, Any, List, Optional
import numpy as np
import chromadb
import traceback

class SimpleVectorDB:
    def __init__(self, db_path="./data/chroma_db"):
        """
        Initialize the Vector Database to manage collections with pre-calculated embeddings.
        
        Args:
            db_path: Path to store the ChromaDB database.
        """
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self.db_path = db_path
        self.current_collection = None
        self.current_collection_name = None
        
        print(f"Vector DB initialized at: {db_path}")
        print(f"Persistence enabled for pre-calculated embeddings.")

    def create_collection(self, collection_name: str, distance_metric: str = 'cosine', description: str = "") -> chromadb.Collection:
        """
        Create or get an existing collection with a specified distance metric.
        
        Args:
            collection_name: Name of the collection.
            distance_metric: The distance metric to use ('cosine' or 'l2'). Defaults to 'cosine'.
            description: Description of what this collection contains.
            
        Returns:
            The collection object.
        """
        metadata = {"description": description} if description else {}
        if distance_metric == 'cosine':
            metadata["hnsw:space"] = "cosine"
        
        collection = self.client.get_or_create_collection(name=collection_name, metadata=metadata)
        print(f"Collection '{collection_name}' ready with distance metric: '{distance_metric}'.")
        return collection

    def use_collection(self, collection_name: str, distance_metric: str = 'cosine', description: str = ""):
        """
        Set the current working collection.
        
        Args:
            collection_name: Name of the collection to use.
            distance_metric: The distance metric for the collection.
            description: Description for new collections.
        """
        self.current_collection = self.create_collection(collection_name, distance_metric, description)
        self.current_collection_name = collection_name
        print(f"Now using collection: {collection_name}")
        
    def load_from_json(self, file_path: str, collection_name: str, model_type: str = 'cohere'):
        """
        Load embeddings from a JSON file into a specified collection.
        Handles normalization based on model type.
        
        Args:
            file_path (str): Path to the JSON embeddings file.
            collection_name (str): Name of the collection to load data into.
            model_type (str): The source of the embeddings ('cohere' or 'openclip'). Defaults to 'cohere'.
        """
        # Determine if normalization is needed based on model type
        normalize_embeddings = (model_type == 'openclip')
        distance_metric = 'cosine' # Defaulting to cosine as requested

        print("-" * 50)
        print(f"🚀 Starting load for '{collection_name}' from '{os.path.basename(file_path)}' (Model: {model_type.upper()})")

        try:
            self.client.delete_collection(name=collection_name)
            print(f"🗑️ Cleared existing collection '{collection_name}' for a fresh load.")
        except Exception:
            pass # It's okay if it didn't exist

        if not os.path.exists(file_path):
            print(f"❌ ERROR: File not found {file_path}. Aborting.")
            return

        try:
            with open(file_path, 'r') as f:
                items = json.load(f).get('items', [])
            
            valid_records = []
            for item in items:
                if 'id' in item and 'metadata' in item and 'embedding' in item and item['embedding']:
                    raw_embedding = item['embedding']
                    final_embedding = raw_embedding[0] if isinstance(raw_embedding[0], list) else raw_embedding
                    valid_records.append({'id': str(item['id']), 'embedding': final_embedding, 'metadata': item['metadata']})
            
            if not valid_records:
                print("❌ No valid records found in file. Aborting.")
                return

            print(f"✅ Found {len(valid_records)} valid records.")

            ids = [r['id'] for r in valid_records]
            metadatas = [r['metadata'] for r in valid_records]
            embeddings = [r['embedding'] for r in valid_records]
            documents = [r['metadata'].get('question', f"Item {r['id']}") for r in valid_records]

            if normalize_embeddings:
                print("🔄 Normalizing embeddings (required for OpenCLIP)...")
                normalized_list = [ (np.array(emb) / np.linalg.norm(emb)).tolist() if np.linalg.norm(emb) > 0 else emb for emb in embeddings ]
                embeddings = normalized_list
                print("✅ Normalization complete.")
            else:
                print("✅ Skipping normalization (assuming pre-normalized embeddings for Cohere).")

            collection = self.create_collection(collection_name, distance_metric=distance_metric)
            
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                collection.add(
                    ids=ids[i:i+batch_size],
                    embeddings=embeddings[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    documents=documents[i:i+batch_size]
                )
            
            print(f"🎉 Successfully loaded {collection.count()} embeddings into '{collection_name}'.")

        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            traceback.print_exc()

    def search_similar_images(
        self, 
        query_embedding: List[float], 
        n_results: int = 5,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Finds similar image embeddings in a collection."""
        if not collection_name and self.current_collection:
            collection_name = self.current_collection_name
        
        if not collection_name:
             raise ValueError("No collection specified or set. Use use_collection() first.")

        collection = self.client.get_collection(name=collection_name)
        
        # We must normalize the query if the collection uses cosine distance
        final_query_embedding = query_embedding
        if collection.metadata.get("hnsw:space") == "cosine":
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                final_query_embedding = (np.array(query_embedding) / norm).tolist()

        results = collection.query(query_embeddings=[final_query_embedding], n_results=n_results)
        
        similar_images = []
        for i, embedding_id in enumerate(results["ids"][0]):
            similar_images.append({
                "id": embedding_id,
                "distance": results["distances"][0][i],
                "metadata": results["metadatas"][0][i]
            })
        
        return {"similar_images": similar_images, "count": len(similar_images), "collection": collection.name}
    
    # ... (other methods like list_collections, get_collection_info, etc., can remain the same) ...
    def list_collections(self) -> List[str]:
        """Lists all collections in the database."""
        collections = self.client.list_collections()
        collection_names = [col.name for col in collections]
        print(f"Available collections: {collection_names}")
        return collection_names

if __name__ == "__main__":
    # --- Example Usage ---
    
    # 1. Initialize the database manager
    db = SimpleVectorDB()

    # 2. Define file paths and collection names
    cohere_validation_file = "notebooks/notebooks/embeddings/lf_vqa_validation_embeddings_cohere.json"
    cohere_train_file = "notebooks/embeddings/lf_vqa_db_embeddings_cohere.json"
    openclip_validation_file = "notebooks/embeddings/lf_vqa_validation_embeddings_openclip.json"
    openclip_train_file = "notebooks/embeddings/lf_vqa_db_embeddings_openclip.json"

    COHERE_VALIDATION_COSINE = "viswiz_validation_cohere_cosine"
    COHERE_TRAIN_COSINE = "viswiz_train_cohere_cosine"
    OPENCLIP_VALIDATION_COSINE = "viswiz_validation_openclip_cosine"
    OPENCLIP_TRAIN_COSINE = "viswiz_train_openclip_cosine"

    # 3. Load the datasets into their respective collections
    
    # Load Cohere data (defaults to 'cohere', no normalization needed)
    db.load_from_json(cohere_validation_file, COHERE_VALIDATION_COSINE)
    db.load_from_json(cohere_train_file, COHERE_TRAIN_COSINE)

    # Load OpenCLIP data (specify model_type='openclip' to trigger normalization)
    db.load_from_json(openclip_validation_file, OPENCLIP_VALIDATION_COSINE, model_type='openclip')
    db.load_from_json(openclip_train_file, OPENCLIP_TRAIN_COSINE, model_type='openclip')

    # 4. Verify the collections were created
    print("\n--- Final Database State ---")
    db.list_collections()