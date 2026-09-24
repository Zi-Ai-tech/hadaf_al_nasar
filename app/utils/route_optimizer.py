import googlemaps
from datetime import datetime
from config import Config
from app.constants import UserType


class DubaiRouteOptimizer:
    def __init__(self):
        self.gmaps = googlemaps.Client(key=Config.GOOGLE_MAPS_API_KEY)
        
    def optimize_routes(self, shipments):
        """
        Optimize delivery routes for Dubai locations
        """
        optimized_routes = []
        
        for shipment in shipments:
            origin = shipment.origin
            destination = shipment.destination
            
            # Get route information
            directions = self.get_directions(origin, destination)
            
            if directions:
                optimized_route = {
                    'shipment_id': shipment.id,
                    'origin': origin,
                    'destination': destination,
                    'distance': directions['distance'],
                    'duration': directions['duration'],
                    'estimated_arrival': directions['estimated_arrival'],
                    'route_coordinates': directions['route_coordinates'],
                    'toll_gates': self.get_dubai_toll_gates(directions['route_coordinates']),
                    'optimized_sequence': self.optimize_delivery_sequence(shipments)
                }
                optimized_routes.append(optimized_route)
        
        return optimized_routes
    
    def get_directions(self, origin, destination):
        """
        Get directions using Google Maps API
        """
        try:
            now = datetime.now()
            directions_result = self.gmaps.directions(
                origin,
                destination,
                mode="driving",
                departure_time=now,
                traffic_model="best_guess"
            )
            
            if directions_result:
                route = directions_result[0]['legs'][0]
                return {
                    'distance': route['distance']['text'],
                    'duration': route['duration']['text'],
                    'estimated_arrival': (now + route['duration']).strftime('%Y-%m-%d %H:%M'),
                    'route_coordinates': self.extract_route_coordinates(directions_result)
                }
        except Exception as e:
            print(f"Error getting directions: {e}")
            return None
    
    def extract_route_coordinates(self, directions_result):
        """
        Extract route coordinates from directions
        """
        coordinates = []
        for step in directions_result[0]['legs'][0]['steps']:
            coordinates.append({
                'lat': step['start_location']['lat'],
                'lng': step['start_location']['lng']
            })
        return coordinates
    
    def get_dubai_toll_gates(self, route_coordinates):
        """
        Check if route passes through Dubai toll gates (Salik)
        """
        salik_locations = [
            {'name': 'Al Barsha', 'lat': 25.1193, 'lng': 55.2011},
            {'name': 'Al Garhoud', 'lat': 25.2279, 'lng': 55.3350},
            {'name': 'Al Maktoum Bridge', 'lat': 25.2654, 'lng': 55.3094},
            {'name': 'Al Mamzar', 'lat': 25.2975, 'lng': 55.3578},
            {'name': 'Al Safa', 'lat': 25.2049, 'lng': 55.2516},
            {'name': 'Airport Tunnel', 'lat': 25.2509, 'lng': 55.3647}
        ]
        
        toll_gates = []
        for toll in salik_locations:
            if self.is_near_route(toll, route_coordinates):
                toll_gates.append(toll['name'])
        
        return toll_gates
    
    def is_near_route(self, point, route_coordinates, threshold_km=2):
        """
        Check if a point is near the route
        """
        # Simplified implementation - in production use proper distance calculation
        for coord in route_coordinates:
            distance = self.calculate_distance(point['lat'], point['lng'], coord['lat'], coord['lng'])
            if distance <= threshold_km:
                return True
        return False
    
    def calculate_distance(self, lat1, lng1, lat2, lng2):
        """
        Calculate distance between two points in kilometers
        """
        from math import radians, sin, cos, sqrt, atan2
        R = 6371  # Earth radius in km
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def optimize_delivery_sequence(self, shipments):
        """
        Implement traveling salesman problem for optimal delivery sequence
        """
        # Simplified implementation - in production use proper TSP algorithm
        return sorted(shipments, key=lambda x: x.priority, reverse=True)