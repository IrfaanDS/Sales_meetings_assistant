import os
from sentence_transformers import SentenceTransformer

def download():
    model_name = 'all-MiniLM-L6-v2'
    # Use a relative path inside the project
    save_path = os.path.join(os.getcwd(), 'model_cache', model_name)
    
    print(f"Downloading model '{model_name}' to {save_path}...")
    
    if not os.path.exists(save_path):
        os.makedirs(save_path, exist_ok=True)
    
    model = SentenceTransformer(model_name)
    model.save(save_path)
    print("Download complete.")

if __name__ == "__main__":
    download()
