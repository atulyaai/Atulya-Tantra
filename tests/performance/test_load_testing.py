"""
Atulya Tantra - Load Testing and Performance Tests
Version: 2.5.0
Performance and load testing for the system
"""

import pytest
import asyncio
import time
import threading
import statistics
from datetime import datetime
import uuid
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import os


class TestLoadTesting:
    """Load testing for the system"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_concurrent_users(self, base_url):
        """Test system under concurrent user load"""
        num_users = 10
        requests_per_user = 5
        
        def user_simulation(user_id):
            """Simulate a single user's behavior"""
            results = []
            
            for i in range(requests_per_user):
                message_data = {
                    "message": f"User {user_id} message {i}",
                    "conversation_id": str(uuid.uuid4()),
                    "user_id": f"user_{user_id}"
                }
                
                start_time = time.time()
                try:
                    response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                    end_time = time.time()
                    
                    results.append({
                        "user_id": user_id,
                        "request_id": i,
                        "status_code": response.status_code,
                        "response_time": end_time - start_time,
                        "success": response.status_code == 200
                    })
                except Exception as e:
                    end_time = time.time()
                    results.append({
                        "user_id": user_id,
                        "request_id": i,
                        "status_code": 0,
                        "response_time": end_time - start_time,
                        "success": False,
                        "error": str(e)
                    })
                
                # Small delay between requests
                time.sleep(0.1)
            
            return results
        
        # Run concurrent users
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(user_simulation, i) for i in range(num_users)]
            all_results = []
            
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        successful_requests = [r for r in all_results if r["success"]]
        failed_requests = [r for r in all_results if not r["success"]]
        
        response_times = [r["response_time"] for r in successful_requests]
        
        # Assertions
        assert len(all_results) == num_users * requests_per_user
        assert len(successful_requests) > 0
        
        # Success rate should be high
        success_rate = len(successful_requests) / len(all_results)
        assert success_rate > 0.8  # 80% success rate
        
        # Response times should be reasonable
        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            
            assert avg_response_time < 5.0  # Average response time < 5 seconds
            assert max_response_time < 15.0  # Max response time < 15 seconds
        
        # Total time should be reasonable
        assert total_time < 60.0  # Total test time < 1 minute
    
    def test_high_volume_requests(self, base_url):
        """Test system under high volume of requests"""
        num_requests = 100
        
        def send_request(request_id):
            """Send a single request"""
            message_data = {
                "message": f"High volume test message {request_id}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "load_test_user"
            }
            
            start_time = time.time()
            try:
                response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                end_time = time.time()
                
                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "status_code": 0,
                    "response_time": end_time - start_time,
                    "success": False,
                    "error": str(e)
                }
        
        # Send requests concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            results = []
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        response_times = [r["response_time"] for r in successful_requests]
        
        # Assertions
        assert len(results) == num_requests
        
        # Success rate should be high
        success_rate = len(successful_requests) / len(results)
        assert success_rate > 0.7  # 70% success rate under high load
        
        # Response times should be reasonable
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            
            assert avg_response_time < 10.0  # Average response time < 10 seconds
            assert p95_response_time < 20.0  # 95th percentile < 20 seconds
        
        # Throughput should be reasonable
        throughput = len(successful_requests) / total_time
        assert throughput > 1.0  # At least 1 request per second
    
    def test_memory_usage(self, base_url):
        """Test memory usage under load"""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Send multiple requests
        num_requests = 50
        results = []
        
        for i in range(num_requests):
            message_data = {
                "message": f"Memory test message {i}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "memory_test_user"
            }
            
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            results.append(response.status_code)
            
            # Check memory usage every 10 requests
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory increase should be reasonable
                assert memory_increase < 100  # Less than 100MB increase
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        # Total memory increase should be reasonable
        assert total_memory_increase < 200  # Less than 200MB total increase
    
    def test_cpu_usage(self, base_url):
        """Test CPU usage under load"""
        # Get initial CPU usage
        initial_cpu = psutil.cpu_percent(interval=1)
        
        # Send multiple requests concurrently
        num_requests = 30
        num_threads = 10
        
        def send_request(request_id):
            """Send a single request"""
            message_data = {
                "message": f"CPU test message {request_id}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "cpu_test_user"
            }
            
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            return response.status_code
        
        # Send requests concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            results = []
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # Check final CPU usage
        final_cpu = psutil.cpu_percent(interval=1)
        
        # CPU usage should be reasonable
        assert final_cpu < 90  # Less than 90% CPU usage


class TestStressTesting:
    """Stress testing for the system"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_sustained_load(self, base_url):
        """Test system under sustained load"""
        duration = 60  # 1 minute
        requests_per_second = 5
        
        start_time = time.time()
        results = []
        
        while time.time() - start_time < duration:
            batch_start = time.time()
            
            # Send a batch of requests
            batch_results = []
            for _ in range(requests_per_second):
                message_data = {
                    "message": f"Sustained load test message",
                    "conversation_id": str(uuid.uuid4()),
                    "user_id": "sustained_test_user"
                }
                
                try:
                    response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                    batch_results.append({
                        "status_code": response.status_code,
                        "success": response.status_code == 200
                    })
                except Exception as e:
                    batch_results.append({
                        "status_code": 0,
                        "success": False,
                        "error": str(e)
                    })
            
            results.extend(batch_results)
            
            # Wait for the rest of the second
            batch_time = time.time() - batch_start
            if batch_time < 1.0:
                time.sleep(1.0 - batch_time)
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        # Success rate should be maintained
        success_rate = len(successful_requests) / len(results)
        assert success_rate > 0.6  # 60% success rate under sustained load
        
        # Should have processed a reasonable number of requests
        expected_requests = duration * requests_per_second
        assert len(results) >= expected_requests * 0.8  # At least 80% of expected requests
    
    def test_peak_load(self, base_url):
        """Test system under peak load"""
        num_requests = 200
        num_threads = 50
        
        def send_request(request_id):
            """Send a single request"""
            message_data = {
                "message": f"Peak load test message {request_id}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "peak_test_user"
            }
            
            start_time = time.time()
            try:
                response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                end_time = time.time()
                
                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "status_code": 0,
                    "response_time": end_time - start_time,
                    "success": False,
                    "error": str(e)
                }
        
        # Send requests with high concurrency
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            results = []
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        # Success rate should be maintained even under peak load
        success_rate = len(successful_requests) / len(results)
        assert success_rate > 0.5  # 50% success rate under peak load
        
        # Should complete within reasonable time
        assert total_time < 120.0  # Total time < 2 minutes
        
        # Throughput should be reasonable
        throughput = len(successful_requests) / total_time
        assert throughput > 0.5  # At least 0.5 requests per second


class TestPerformanceMetrics:
    """Test performance metrics"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_response_time_metrics(self, base_url):
        """Test response time metrics"""
        num_requests = 20
        response_times = []
        
        for i in range(num_requests):
            message_data = {
                "message": f"Response time test message {i}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "response_time_test_user"
            }
            
            start_time = time.time()
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            end_time = time.time()
            
            if response.status_code == 200:
                response_times.append(end_time - start_time)
        
        # Calculate metrics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
            
            # Assertions
            assert avg_response_time < 3.0  # Average response time < 3 seconds
            assert median_response_time < 2.0  # Median response time < 2 seconds
            assert p95_response_time < 5.0  # 95th percentile < 5 seconds
            assert p99_response_time < 10.0  # 99th percentile < 10 seconds
    
    def test_throughput_metrics(self, base_url):
        """Test throughput metrics"""
        duration = 30  # 30 seconds
        start_time = time.time()
        request_count = 0
        
        while time.time() - start_time < duration:
            message_data = {
                "message": f"Throughput test message {request_count}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "throughput_test_user"
            }
            
            response = requests.post(f"{base_url}/api/chat/send", json=message_data)
            if response.status_code == 200:
                request_count += 1
            
            time.sleep(0.1)  # Small delay between requests
        
        actual_duration = time.time() - start_time
        throughput = request_count / actual_duration
        
        # Throughput should be reasonable
        assert throughput > 0.5  # At least 0.5 requests per second
    
    def test_error_rate_metrics(self, base_url):
        """Test error rate metrics"""
        num_requests = 50
        successful_requests = 0
        failed_requests = 0
        
        for i in range(num_requests):
            message_data = {
                "message": f"Error rate test message {i}",
                "conversation_id": str(uuid.uuid4()),
                "user_id": "error_rate_test_user"
            }
            
            try:
                response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                if response.status_code == 200:
                    successful_requests += 1
                else:
                    failed_requests += 1
            except Exception:
                failed_requests += 1
        
        error_rate = failed_requests / num_requests
        
        # Error rate should be low
        assert error_rate < 0.1  # Less than 10% error rate
    
    def test_health_check_performance(self, base_url):
        """Test health check performance"""
        num_requests = 20
        response_times = []
        
        for _ in range(num_requests):
            start_time = time.time()
            response = requests.get(f"{base_url}/api/health")
            end_time = time.time()
            
            if response.status_code == 200:
                response_times.append(end_time - start_time)
        
        # Health check should be very fast
        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            
            assert avg_response_time < 0.5  # Average response time < 0.5 seconds
            assert max_response_time < 1.0  # Max response time < 1 second


class TestScalability:
    """Test system scalability"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_scalability_with_users(self, base_url):
        """Test scalability with increasing number of users"""
        user_counts = [1, 5, 10, 20]
        requests_per_user = 3
        
        results = {}
        
        for num_users in user_counts:
            def user_simulation(user_id):
                """Simulate a single user's behavior"""
                user_results = []
                
                for i in range(requests_per_user):
                    message_data = {
                        "message": f"Scalability test user {user_id} message {i}",
                        "conversation_id": str(uuid.uuid4()),
                        "user_id": f"scalability_user_{user_id}"
                    }
                    
                    start_time = time.time()
                    try:
                        response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                        end_time = time.time()
                        
                        user_results.append({
                            "status_code": response.status_code,
                            "response_time": end_time - start_time,
                            "success": response.status_code == 200
                        })
                    except Exception as e:
                        end_time = time.time()
                        user_results.append({
                            "status_code": 0,
                            "response_time": end_time - start_time,
                            "success": False,
                            "error": str(e)
                        })
                
                return user_results
            
            # Run concurrent users
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=num_users) as executor:
                futures = [executor.submit(user_simulation, i) for i in range(num_users)]
                all_results = []
                
                for future in as_completed(futures):
                    results = future.result()
                    all_results.extend(results)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Analyze results
            successful_requests = [r for r in all_results if r["success"]]
            success_rate = len(successful_requests) / len(all_results)
            
            results[num_users] = {
                "total_requests": len(all_results),
                "successful_requests": len(successful_requests),
                "success_rate": success_rate,
                "total_time": total_time,
                "throughput": len(successful_requests) / total_time
            }
        
        # Verify scalability
        for num_users in user_counts:
            result = results[num_users]
            
            # Success rate should remain high
            assert result["success_rate"] > 0.7  # 70% success rate
            
            # Throughput should be reasonable
            assert result["throughput"] > 0.1  # At least 0.1 requests per second
    
    def test_scalability_with_requests(self, base_url):
        """Test scalability with increasing number of requests"""
        request_counts = [10, 25, 50, 100]
        
        results = {}
        
        for num_requests in request_counts:
            def send_request(request_id):
                """Send a single request"""
                message_data = {
                    "message": f"Scalability test request {request_id}",
                    "conversation_id": str(uuid.uuid4()),
                    "user_id": "scalability_test_user"
                }
                
                start_time = time.time()
                try:
                    response = requests.post(f"{base_url}/api/chat/send", json=message_data)
                    end_time = time.time()
                    
                    return {
                        "status_code": response.status_code,
                        "response_time": end_time - start_time,
                        "success": response.status_code == 200
                    }
                except Exception as e:
                    end_time = time.time()
                    return {
                        "status_code": 0,
                        "response_time": end_time - start_time,
                        "success": False,
                        "error": str(e)
                    }
            
            # Send requests concurrently
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=min(num_requests, 20)) as executor:
                futures = [executor.submit(send_request, i) for i in range(num_requests)]
                all_results = []
                
                for future in as_completed(futures):
                    result = future.result()
                    all_results.append(result)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Analyze results
            successful_requests = [r for r in all_results if r["success"]]
            success_rate = len(successful_requests) / len(all_results)
            
            results[num_requests] = {
                "total_requests": len(all_results),
                "successful_requests": len(successful_requests),
                "success_rate": success_rate,
                "total_time": total_time,
                "throughput": len(successful_requests) / total_time
            }
        
        # Verify scalability
        for num_requests in request_counts:
            result = results[num_requests]
            
            # Success rate should remain high
            assert result["success_rate"] > 0.6  # 60% success rate
            
            # Throughput should be reasonable
            assert result["throughput"] > 0.1  # At least 0.1 requests per second


if __name__ == "__main__":
    pytest.main([__file__])
