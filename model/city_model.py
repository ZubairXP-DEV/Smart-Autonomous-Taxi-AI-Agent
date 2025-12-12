"""
Main city simulation model with agents and road network.
"""

import random
from mesa import Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import networkx as nx

from agents.taxi import Taxi
from agents.passenger import Passenger
from agents.traffic_light import TrafficLight
from utils.pathfinding import create_road_network, get_random_road_position
from analytics.data_collector import SimulationDataCollector


class CityModel(Model):
    """
    Main model for the Smart Autonomous Taxi & Traffic System.
    """
    
    def __init__(self, width=30, height=30, num_taxis=10, num_traffic_lights=8, 
                 passenger_spawn_rate=0.1, enable_rush_hour=True, enable_weather=False):
        super().__init__()
        
        # Model parameters
        self.width = width
        self.height = height
        self.num_taxis = num_taxis
        self.num_traffic_lights = num_traffic_lights
        self.passenger_spawn_rate = passenger_spawn_rate
        self.enable_rush_hour = enable_rush_hour
        self.enable_weather = enable_weather
        
        # Rush hour settings
        self.rush_hour_active = False
        self.rush_hour_multiplier = 2.0  # 2x spawn rate during rush hour
        
        # Weather settings
        self.weather = "clear"  # "clear", "rain", "snow"
        self.weather_speed_modifier = 1.0
        
        # Create grid and road network
        self.grid = MultiGrid(width, height, True)
        self.road_network = create_road_network(width, height)
        
        # Schedule for agent activation
        self.schedule = RandomActivation(self)
        
        # Data collector for custom analytics
        self.custom_datacollector = SimulationDataCollector()
        
        # Mesa DataCollector for charts (must be named 'datacollector' for Mesa charts)
        self.datacollector = DataCollector(
            model_reporters={
                "Waiting_Passengers": lambda m: len([a for a in m.schedule.agents 
                                                     if isinstance(a, Passenger) and a.status == "waiting"]),
                "Active_Taxis": lambda m: len([a for a in m.schedule.agents 
                                               if isinstance(a, Taxi) and a.status != "idle"]),
                "Avg_Wait_Time": lambda m: self._calculate_avg_wait_time(),
                "Taxi_Utilization": lambda m: self._calculate_taxi_utilization(),
                "Traffic_Density": lambda m: self._calculate_traffic_density(),
            },
            agent_reporters={
                "Status": lambda a: a.status if hasattr(a, 'status') else None,
            }
        )
        
        # Initialize agents
        self._create_taxis()
        self._create_traffic_lights()
        
        # Track intersections for traffic lights
        self.intersections = self._identify_intersections()
        
        # Running statistics
        self.running = True
        
    def _create_taxis(self):
        """Create taxi agents at random road positions with different types."""
        taxi_types = ["economy", "premium", "luxury"]
        for i in range(self.num_taxis):
            pos = get_random_road_position(self.road_network)
            if pos:
                # Distribute taxi types: 60% economy, 30% premium, 10% luxury
                if i < int(self.num_taxis * 0.6):
                    taxi_type = "economy"
                elif i < int(self.num_taxis * 0.9):
                    taxi_type = "premium"
                else:
                    taxi_type = "luxury"
                
                taxi = Taxi(i, self, pos, taxi_type=taxi_type)
                self.schedule.add(taxi)
                self.grid.place_agent(taxi, pos)
    
    def _create_traffic_lights(self):
        """Create traffic light agents at intersections."""
        intersections = self._identify_intersections()
        selected_intersections = random.sample(
            intersections, min(self.num_traffic_lights, len(intersections))
        )
        
        for i, intersection in enumerate(selected_intersections):
            # Alternate between horizontal and vertical control
            direction = "horizontal" if i % 2 == 0 else "vertical"
            traffic_light = TrafficLight(f"tl_{i}", self, intersection, direction)
            self.schedule.add(traffic_light)
            self.grid.place_agent(traffic_light, intersection)
    
    def _identify_intersections(self):
        """Identify intersection points in the road network."""
        intersections = []
        for node in self.road_network.nodes():
            # Count neighbors (degree) - intersections have degree > 2
            degree = self.road_network.degree(node)
            if degree >= 3:  # Intersection point
                intersections.append(node)
        return intersections if intersections else list(self.road_network.nodes())[:self.num_traffic_lights]
    
    def step(self):
        """Execute one step of the simulation."""
        # Update rush hour status
        if self.enable_rush_hour:
            self._update_rush_hour()
        
        # Update weather (random changes)
        if self.enable_weather:
            self._update_weather()
        
        # Calculate effective spawn rate (rush hour multiplier)
        effective_spawn_rate = self.passenger_spawn_rate
        if self.rush_hour_active:
            effective_spawn_rate *= self.rush_hour_multiplier
        
        # Spawn new passengers
        if random.random() < effective_spawn_rate:
            self._spawn_passenger()
        
        # Advance all agents
        self.schedule.step()
        
        # Collect data
        self.custom_datacollector.collect_step_data(self)
        self.datacollector.collect(self)
        
        # Stop after reasonable number of steps (optional)
        if self.schedule.time >= 1000:
            self.running = False
    
    def _update_rush_hour(self):
        """Update rush hour status based on simulation time."""
        step = self.schedule.time
        # Rush hours: steps 50-150 (morning) and 300-400 (evening)
        if (50 <= step <= 150) or (300 <= step <= 400):
            self.rush_hour_active = True
        else:
            self.rush_hour_active = False
    
    def _update_weather(self):
        """Randomly change weather conditions."""
        if random.random() < 0.01:  # 1% chance per step
            weathers = ["clear", "rain", "snow"]
            self.weather = random.choice(weathers)
            # Weather affects movement speed
            if self.weather == "rain":
                self.weather_speed_modifier = 0.8  # 20% slower
            elif self.weather == "snow":
                self.weather_speed_modifier = 0.6  # 40% slower
            else:
                self.weather_speed_modifier = 1.0
    
    def _calculate_avg_wait_time(self):
        """Calculate average wait time for waiting passengers."""
        waiting_passengers = [a for a in self.schedule.agents 
                             if isinstance(a, Passenger) and a.status == "waiting"]
        if waiting_passengers:
            return sum(p.wait_time for p in waiting_passengers) / len(waiting_passengers)
        return 0
    
    def _calculate_taxi_utilization(self):
        """Calculate taxi utilization percentage."""
        taxis = [a for a in self.schedule.agents if isinstance(a, Taxi)]
        if taxis:
            active = sum(1 for t in taxis if t.status != "idle")
            return (active / len(taxis)) * 100
        return 0
    
    def _calculate_traffic_density(self):
        """Calculate traffic density (vehicles per cell)."""
        from agents.taxi import Taxi
        occupied_cells = 0
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                cell_contents = self.grid.get_cell_list_contents([(x, y)])
                if any(isinstance(a, Taxi) for a in cell_contents):
                    occupied_cells += 1
        total_cells = self.width * self.height
        return (occupied_cells / total_cells) * 100 if total_cells > 0 else 0
    
    def _spawn_passenger(self):
        """Spawn a new passenger with random priority."""
        start_pos = get_random_road_position(self.road_network)
        end_pos = get_random_road_position(self.road_network)
        
        # Ensure start and end are different
        while end_pos == start_pos:
            end_pos = get_random_road_position(self.road_network)
        
        if start_pos and end_pos:
            # Assign priority: 5% emergency, 15% VIP, 80% regular
            rand = random.random()
            if rand < 0.05:
                priority = "emergency"
            elif rand < 0.20:
                priority = "vip"
            else:
                priority = "regular"
            
            passenger_id = f"passenger_{self.schedule.time}_{random.randint(1000, 9999)}"
            passenger = Passenger(passenger_id, self, start_pos, end_pos, priority=priority)
            self.schedule.add(passenger)
            self.grid.place_agent(passenger, start_pos)

