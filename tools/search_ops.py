import os

class SearchTool:
    @staticmethod
    def local_search(query, path="."):
        results = []
        for root, dirs, files in os.walk(path):
            if "memory" in root or "logs" in root or "__pycache__" in root:
                continue
            for file in files:
                if query.lower() in file.lower():
                    results.append(os.path.join(root, file))
        
        if results:
            return f"Found relevant files: {', '.join(results)}"
        return "No local results found. (Web search disabled in v0)"
