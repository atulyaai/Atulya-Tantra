class Critic:
    def verify(self, task, results):
        # Verify if results meet the task requirements
        if "Success" in results:
            return True, "Task verified successfully"
        return False, "Task failed verification"
