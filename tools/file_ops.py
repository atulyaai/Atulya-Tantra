import os

class FileOps:
    @staticmethod
    def read_file(path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return "Error: File not found"

    @staticmethod
    def write_file(path, content):
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Success: File written to {path}"
        except Exception as e:
            return f"Error: {str(e)}"
