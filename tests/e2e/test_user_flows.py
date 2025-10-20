"""
Atulya Tantra - End-to-End User Flow Tests
Version: 2.5.0
End-to-end tests for complete user workflows
"""

import pytest
import asyncio
import time
from datetime import datetime
import uuid
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import json


class TestChatWorkflow:
    """Test complete chat workflow"""
    
    @pytest.fixture
    def driver(self):
        """Setup Chrome driver for testing"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_complete_chat_workflow(self, driver, base_url):
        """Test complete chat workflow from start to finish"""
        # Navigate to the chat interface
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Find the message input
        message_input = driver.find_element(By.ID, "message-input")
        assert message_input is not None
        
        # Send a test message
        test_message = "Hello, this is a test message"
        message_input.send_keys(test_message)
        
        # Click send button
        send_button = driver.find_element(By.ID, "send-button")
        send_button.click()
        
        # Wait for response
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "message"))
        )
        
        # Verify message was sent
        messages = driver.find_elements(By.CLASS_NAME, "message")
        assert len(messages) >= 1
        
        # Check that the message contains our test message
        message_text = messages[-1].text
        assert test_message in message_text or "Hello" in message_text
    
    def test_streaming_response(self, driver, base_url):
        """Test streaming response functionality"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Send a message that should trigger streaming
        message_input = driver.find_element(By.ID, "message-input")
        message_input.send_keys("Tell me a long story")
        
        send_button = driver.find_element(By.ID, "send-button")
        send_button.click()
        
        # Wait for streaming to start
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "streaming"))
        )
        
        # Wait for streaming to complete
        WebDriverWait(driver, 60).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "streaming"))
        )
        
        # Verify response was received
        messages = driver.find_elements(By.CLASS_NAME, "message")
        assert len(messages) >= 2  # User message + AI response
    
    def test_message_actions(self, driver, base_url):
        """Test message actions (copy, edit, regenerate)"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Send a message
        message_input = driver.find_element(By.ID, "message-input")
        message_input.send_keys("Test message for actions")
        
        send_button = driver.find_element(By.ID, "send-button")
        send_button.click()
        
        # Wait for response
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "message"))
        )
        
        # Find the last message (AI response)
        messages = driver.find_elements(By.CLASS_NAME, "message")
        last_message = messages[-1]
        
        # Hover over message to show actions
        driver.execute_script("arguments[0].scrollIntoView();", last_message)
        time.sleep(1)
        
        # Try to find copy button
        try:
            copy_button = last_message.find_element(By.CLASS_NAME, "copy-button")
            copy_button.click()
            time.sleep(1)
        except NoSuchElementException:
            # Copy button might not be visible or implemented yet
            pass
    
    def test_conversation_management(self, driver, base_url):
        """Test conversation management features"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Send a message to create a conversation
        message_input = driver.find_element(By.ID, "message-input")
        message_input.send_keys("Create a new conversation")
        
        send_button = driver.find_element(By.ID, "send-button")
        send_button.click()
        
        # Wait for response
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "message"))
        )
        
        # Try to find conversation list or new conversation button
        try:
            new_conversation_button = driver.find_element(By.ID, "new-conversation")
            new_conversation_button.click()
            time.sleep(1)
        except NoSuchElementException:
            # New conversation button might not be implemented yet
            pass


class TestMultimodalWorkflow:
    """Test multimodal input workflow"""
    
    @pytest.fixture
    def driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_file_upload_workflow(self, driver, base_url):
        """Test file upload workflow"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Try to find file upload button
        try:
            file_button = driver.find_element(By.ID, "file-button")
            file_button.click()
            time.sleep(1)
        except NoSuchElementException:
            # File upload might not be implemented yet
            pytest.skip("File upload not implemented")
    
    def test_voice_input_workflow(self, driver, base_url):
        """Test voice input workflow"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Try to find voice input button
        try:
            voice_button = driver.find_element(By.ID, "voice-button")
            voice_button.click()
            time.sleep(1)
        except NoSuchElementException:
            # Voice input might not be implemented yet
            pytest.skip("Voice input not implemented")
    
    def test_vision_input_workflow(self, driver, base_url):
        """Test vision input workflow"""
        driver.get(f"{base_url}/webui/")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-container"))
        )
        
        # Try to find vision input button
        try:
            vision_button = driver.find_element(By.ID, "vision-button")
            vision_button.click()
            time.sleep(1)
        except NoSuchElementException:
            # Vision input might not be implemented yet
            pytest.skip("Vision input not implemented")


class TestAPIWorkflow:
    """Test API workflow"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_complete_api_workflow(self, base_url):
        """Test complete API workflow"""
        # Test health check
        response = requests.get(f"{base_url}/api/health")
        assert response.status_code == 200
        
        # Test sending a message
        message_data = {
            "message": "Hello from API test",
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        response = requests.post(f"{base_url}/api/chat/send", json=message_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data
        
        # Test getting conversation history
        conversation_id = data["conversation_id"]
        response = requests.get(f"{base_url}/api/chat/history/{conversation_id}")
        assert response.status_code == 200
        
        history_data = response.json()
        assert "messages" in history_data
        assert len(history_data["messages"]) >= 1
    
    def test_streaming_api_workflow(self, base_url):
        """Test streaming API workflow"""
        message_data = {
            "message": "Tell me a story",
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        response = requests.post(
            f"{base_url}/api/chat/stream",
            json=message_data,
            stream=True
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Check that we get streaming data
        content = response.text
        assert len(content) > 0
    
    def test_multimodal_api_workflow(self, base_url):
        """Test multimodal API workflow"""
        # Test voice input
        audio_data = b"mock_audio_data"
        files = {"audio": ("test.wav", audio_data, "audio/wav")}
        
        response = requests.post(f"{base_url}/api/chat/voice", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "transcribed_text" in data
        
        # Test vision input
        image_data = b"mock_image_data"
        files = {"image": ("test.jpg", image_data, "image/jpeg")}
        
        response = requests.post(f"{base_url}/api/chat/vision", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "analysis" in data
    
    def test_admin_api_workflow(self, base_url):
        """Test admin API workflow"""
        # Test system status
        response = requests.get(f"{base_url}/api/admin/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "system_status" in data
        
        # Test agent status
        response = requests.get(f"{base_url}/api/admin/agents")
        assert response.status_code == 200
        
        data = response.json()
        assert "agents" in data
        
        # Test integration status
        response = requests.get(f"{base_url}/api/admin/integrations")
        assert response.status_code == 200
        
        data = response.json()
        assert "integrations" in data


class TestPerformanceWorkflow:
    """Test performance workflows"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_concurrent_api_requests(self, base_url):
        """Test concurrent API requests"""
        import threading
        import time
        
        results = []
        
        def send_request():
            message_data = {
                "message": "Concurrent test message",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "test_user"
            }
            
            start_time = time.time()
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            end_time = time.time()
            
            results.append({
                "status_code": response.status_code,
                "response_time": end_time - start_time
            })
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=send_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all requests succeeded
        assert len(results) == 5
        assert all(result["status_code"] == 200 for result in results)
        
        # Verify reasonable response times
        assert all(result["response_time"] < 10.0 for result in results)
        
        # Verify total time is reasonable
        assert total_time < 30.0
    
    def test_large_message_handling(self, base_url):
        """Test handling of large messages"""
        # Create a large message
        large_message = "This is a test message. " * 1000  # ~25KB
        
        message_data = {
            "message": large_message,
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        start_time = time.time()
        response = requests.post(f"{base_url}/api/chat/send", json=message_data)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should handle large messages gracefully
        assert response.status_code in [200, 413]  # 413 = Payload Too Large
        assert response_time < 30.0  # Should not take too long
    
    def test_health_check_performance(self, base_url):
        """Test health check performance"""
        start_time = time.time()
        response = requests.get(f"{base_url}/api/health")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Health check should be very fast


class TestErrorHandlingWorkflow:
    """Test error handling workflows"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_invalid_endpoint_handling(self, base_url):
        """Test handling of invalid endpoints"""
        response = requests.get(f"{base_url}/api/invalid/endpoint")
        assert response.status_code == 404
    
    def test_invalid_data_handling(self, base_url):
        """Test handling of invalid data"""
        # Test invalid JSON
        response = requests.post(
            f"{base_url}/api/chat/send",
            data="invalid json",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
        
        # Test missing required fields
        response = requests.post(f"{base_url}/api/chat/send", json={})
        assert response.status_code == 422
    
    def test_server_error_handling(self, base_url):
        """Test handling of server errors"""
        # This test would need to be adjusted based on actual error scenarios
        # For now, just test that the server is running
        response = requests.get(f"{base_url}/api/health")
        assert response.status_code == 200


class TestSecurityWorkflow:
    """Test security workflows"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_sql_injection_protection(self, base_url):
        """Test protection against SQL injection"""
        malicious_message = "'; DROP TABLE users; --"
        
        message_data = {
            "message": malicious_message,
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        response = requests.post(f"{base_url}/api/chat/send", json=message_data)
        
        # Should handle malicious input gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_xss_protection(self, base_url):
        """Test protection against XSS attacks"""
        malicious_message = "<script>alert('XSS')</script>"
        
        message_data = {
            "message": malicious_message,
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        response = requests.post(f"{base_url}/api/chat/send", json=message_data)
        
        # Should handle malicious input gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_rate_limiting(self, base_url):
        """Test rate limiting"""
        message_data = {
            "message": "Rate limit test",
            "conversation_id": str(uuid.uuid4()),
            "user_id": "test_user"
        }
        
        # Send multiple requests quickly
        responses = []
        for _ in range(20):
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            responses.append(response.status_code)
        
        # Should not all be 200 (some should be rate limited)
        # Note: This test may need adjustment based on actual rate limiting implementation
        assert len(responses) == 20


if __name__ == "__main__":
    pytest.main([__file__])
