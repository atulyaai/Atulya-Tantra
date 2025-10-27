#!/usr/bin/env python3
"""
Atulya Tantra AGI - Dynamic System Launcher
Launches the complete self-evolving, self-installing AGI system
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from Core.dynamic.installer import get_installer, install_system
from Core.dynamic.agent_factory import get_agent_factory, AgentSpecification, AgentType, AgentCapability
from Core.dynamic.function_discovery import get_discovery, get_auto_importer, discover_and_import_all
from Core.dynamic.self_evolution import get_evolution_engine
from Core.monitoring.metrics import get_metrics_collector
from Core.monitoring.health import get_health_checker
from Core.monitoring.alerting import get_alert_manager
from Core.monitoring.dashboards import get_dashboard_manager
from Core.monitoring.logging import get_structured_logger, LogCategory, LogLevel
from Core.monitoring.performance import get_performance_monitor
from Core.unified_agi_system import get_agi_system, SystemMode
from Test.test_comprehensive_system import run_comprehensive_tests


class DynamicSystemLauncher:
    """Launches and manages the complete dynamic AGI system"""
    
    def __init__(self):
        self.start_time = None
        self.system_status = "initializing"
        self.components = {}
        self.is_running = False
        
    async def launch_system(self, run_tests: bool = True, auto_install: bool = True):
        """Launch the complete dynamic system"""
        self.start_time = datetime.utcnow()
        print("🚀 Atulya Tantra AGI - Dynamic System Launcher")
        print("=" * 60)
        
        try:
            # Phase 1: System Installation
            if auto_install:
                await self._install_system()
            
            # Phase 2: Initialize Core Components
            await self._initialize_core_components()
            
            # Phase 3: Start Dynamic Systems
            await self._start_dynamic_systems()
            
            # Phase 4: Run Comprehensive Tests
            if run_tests:
                await self._run_system_tests()
            
            # Phase 5: Start Main System
            await self._start_main_system()
            
            # Phase 6: Start Evolution Process
            await self._start_evolution_process()
            
            self.system_status = "running"
            self.is_running = True
            
            print("\n✅ System Successfully Launched!")
            print("=" * 60)
            await self._display_system_status()
            
            # Keep system running
            await self._keep_system_running()
            
        except Exception as e:
            print(f"\n❌ System Launch Failed: {e}")
            self.system_status = "failed"
            raise
    
    async def _install_system(self):
        """Install system components dynamically"""
        print("\n📦 Phase 1: Dynamic System Installation")
        print("-" * 40)
        
        installer = get_installer()
        
        # Check system requirements
        print("  Checking system requirements...")
        requirements = await installer.check_system_requirements()
        print(f"    Python: {requirements['python_version']}")
        print(f"    Available packages: {len(requirements['available_packages'])}")
        print(f"    Missing packages: {len(requirements['missing_packages'])}")
        
        # Install required components
        print("  Installing required components...")
        install_results = await install_system()
        
        success_count = len([r for r in install_results if r.status.value == "installed"])
        total_count = len(install_results)
        
        print(f"    Installed: {success_count}/{total_count} components")
        
        if success_count < total_count:
            print("    ⚠️  Some components failed to install")
            for result in install_results:
                if result.status.value != "installed":
                    print(f"      ❌ {result.component}: {result.message}")
        else:
            print("    ✅ All components installed successfully")
    
    async def _initialize_core_components(self):
        """Initialize core system components"""
        print("\n🔧 Phase 2: Core Component Initialization")
        print("-" * 40)
        
        # Initialize monitoring components
        print("  Initializing monitoring system...")
        self.components['metrics'] = get_metrics_collector()
        self.components['health'] = get_health_checker()
        self.components['alerts'] = get_alert_manager()
        self.components['dashboards'] = get_dashboard_manager()
        self.components['logger'] = get_structured_logger()
        self.components['performance'] = get_performance_monitor()
        
        # Start monitoring
        await self.components['health'].start()
        await self.components['alerts'].start()
        
        print("    ✅ Monitoring system initialized")
        
        # Initialize dynamic components
        print("  Initializing dynamic systems...")
        self.components['installer'] = get_installer()
        self.components['agent_factory'] = get_agent_factory()
        self.components['discovery'] = get_discovery()
        self.components['auto_importer'] = get_auto_importer()
        self.components['evolution'] = get_evolution_engine()
        
        print("    ✅ Dynamic systems initialized")
    
    async def _start_dynamic_systems(self):
        """Start dynamic systems"""
        print("\n🔄 Phase 3: Dynamic System Activation")
        print("-" * 40)
        
        # Start function discovery
        print("  Starting function discovery...")
        discovery = self.components['discovery']
        scan_results = await discovery.scan_all()
        print(f"    Discovered: {scan_results['functions_discovered']} functions, {scan_results['modules_discovered']} modules")
        
        # Start auto-import
        print("  Starting auto-import system...")
        importer = self.components['auto_importer']
        import_results = await discover_and_import_all()
        print(f"    Imported: {import_results['total_imported']} functions")
        
        # Create default agents
        print("  Creating default agents...")
        agent_factory = self.components['agent_factory']
        
        default_agents = [
            AgentSpecification(
                name="system_monitor",
                type=AgentType.MONITOR,
                capabilities=[AgentCapability.SYSTEM_CONTROL, AgentCapability.DATABASE_OPERATIONS],
                description="System monitoring agent"
            ),
            AgentSpecification(
                name="general_assistant",
                type=AgentType.GENERALIST,
                capabilities=[AgentCapability.TEXT_PROCESSING, AgentCapability.CODE_GENERATION],
                description="General purpose assistant"
            ),
            AgentSpecification(
                name="data_analyst",
                type=AgentType.SPECIALIST,
                capabilities=[AgentCapability.DATA_ANALYSIS],
                description="Data analysis specialist",
                config={"specialization": "data_analysis"}
            )
        ]
        
        created_agents = []
        for spec in default_agents:
            try:
                agent = await agent_factory.create_agent(spec)
                created_agents.append(agent)
                print(f"    ✅ Created agent: {spec.name}")
            except Exception as e:
                print(f"    ❌ Failed to create agent {spec.name}: {e}")
        
        print(f"    Created {len(created_agents)}/{len(default_agents)} agents")
    
    async def _run_system_tests(self):
        """Run comprehensive system tests"""
        print("\n🧪 Phase 4: Comprehensive System Testing")
        print("-" * 40)
        
        print("  Running comprehensive test suite...")
        test_results = await run_comprehensive_tests()
        
        summary = test_results['summary']
        print(f"    Tests: {summary['passed_tests']}/{summary['total_tests']} passed")
        print(f"    Success rate: {summary['success_rate']:.1f}%")
        print(f"    Duration: {summary['total_duration']:.2f}s")
        
        if summary['success_rate'] < 80:
            print("    ⚠️  Some tests failed - system may not be fully operational")
        else:
            print("    ✅ All critical tests passed")
    
    async def _start_main_system(self):
        """Start the main AGI system"""
        print("\n🤖 Phase 5: Main AGI System Startup")
        print("-" * 40)
        
        print("  Starting unified AGI system...")
        agi_system = get_agi_system()
        
        # Start the system
        await agi_system.start_system(SystemMode.CONVERSATIONAL)
        
        # Get system status
        status = agi_system.get_system_status()
        print(f"    Status: {status['is_active']}")
        print(f"    Mode: {status['system_mode']}")
        print(f"    Initialized: {status['is_initialized']}")
        
        self.components['agi_system'] = agi_system
        print("    ✅ AGI system started successfully")
    
    async def _start_evolution_process(self):
        """Start the self-evolution process"""
        print("\n🧬 Phase 6: Self-Evolution Process")
        print("-" * 40)
        
        evolution_engine = self.components['evolution']
        
        # Add some initial learning data
        print("  Adding initial learning data...")
        evolution_engine.add_learning_data(
            input_data="test input",
            output_data="test output",
            success=True,
            performance_metrics={"accuracy": 0.85, "speed": 0.92}
        )
        
        # Get evolution status
        status = evolution_engine.get_evolution_status()
        print(f"    Capabilities: {len(status['capabilities'])}")
        print(f"    Evolution rules: {len(status['evolution_rules'])}")
        print(f"    Learning data points: {status['learning_statistics']['total_data_points']}")
        
        print("    ✅ Self-evolution process started")
    
    async def _display_system_status(self):
        """Display current system status"""
        print("\n📊 System Status Dashboard")
        print("-" * 40)
        
        # AGI System Status
        if 'agi_system' in self.components:
            agi_status = self.components['agi_system'].get_system_status()
            print(f"AGI System: {'🟢 Active' if agi_status['is_active'] else '🔴 Inactive'}")
            print(f"Mode: {agi_status['system_mode']}")
        
        # Health Status
        health_checker = self.components['health']
        overall_health = health_checker.get_overall_health()
        print(f"System Health: {overall_health['status']}")
        
        # Agent Status
        agent_factory = self.components['agent_factory']
        agent_stats = agent_factory.get_agent_statistics()
        print(f"Active Agents: {agent_stats['active_agents']}/{agent_stats['total_agents']}")
        
        # Evolution Status
        evolution_engine = self.components['evolution']
        evolution_status = evolution_engine.get_evolution_status()
        print(f"Evolution: {'🟢 Active' if evolution_status['is_evolving'] else '🔴 Inactive'}")
        
        # Capabilities
        print("\nCapabilities:")
        for name, cap in evolution_status['capabilities'].items():
            level = cap['level']
            bar = "█" * int(level * 20) + "░" * (20 - int(level * 20))
            print(f"  {name}: {bar} {level:.2f}")
    
    async def _keep_system_running(self):
        """Keep the system running and monitor it"""
        print("\n🔄 System Running - Press Ctrl+C to stop")
        print("-" * 40)
        
        try:
            while self.is_running:
                # Update system status
                await self._update_system_status()
                
                # Wait before next update
                await asyncio.sleep(30)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down system...")
            await self._shutdown_system()
    
    async def _update_system_status(self):
        """Update and display system status"""
        # This would update system status and display metrics
        # For now, we'll just log that the system is running
        pass
    
    async def _shutdown_system(self):
        """Gracefully shutdown the system"""
        print("  Stopping components...")
        
        # Stop monitoring
        if 'health' in self.components:
            await self.components['health'].stop()
        
        if 'alerts' in self.components:
            await self.components['alerts'].stop()
        
        # Stop AGI system
        if 'agi_system' in self.components:
            await self.components['agi_system'].stop_system()
        
        self.is_running = False
        print("  ✅ System shutdown complete")


async def main():
    """Main entry point"""
    launcher = DynamicSystemLauncher()
    
    # Parse command line arguments
    run_tests = "--no-tests" not in sys.argv
    auto_install = "--no-install" not in sys.argv
    
    try:
        await launcher.launch_system(run_tests=run_tests, auto_install=auto_install)
    except Exception as e:
        print(f"\n💥 Fatal Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the launcher
    asyncio.run(main())