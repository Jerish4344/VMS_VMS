from django.views.generic import TemplateView
from vehicles.models import Vehicle, Firm
from trips.models import Trip
from django.utils import timezone
from datetime import datetime, timedelta
from accounts.permissions import FirmReportPermissionMixin

class FirmReportView(FirmReportPermissionMixin, TemplateView):
    paginate_by = 30
    template_name = 'reports/firm_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        firm_id = self.request.GET.get('firm')
        vehicle_id = self.request.GET.get('vehicle')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        firms = Firm.objects.all()
        context['firms'] = firms
        context['selected_firm'] = None
        context['vehicles'] = []
        context['selected_vehicle'] = None
        context['trips'] = []
        context['trip_data'] = []  # Initialize trip_data here

        if firm_id:
            try:
                firm = Firm.objects.get(id=firm_id)
                context['selected_firm'] = firm
                vehicles = Vehicle.objects.filter(firms=firm)
                context['vehicles'] = vehicles
                if vehicle_id:
                    try:
                        vehicle = vehicles.get(id=vehicle_id)
                        context['selected_vehicle'] = vehicle
                        trips = Trip.objects.filter(vehicle=vehicle, is_deleted=False)
                        if start_date:
                            trips = trips.filter(start_time__date__gte=start_date)
                        if end_date:
                            trips = trips.filter(start_time__date__lte=end_date)
                        from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
                        paginator = Paginator(trips, self.paginate_by)
                        page = self.request.GET.get('page')
                        try:
                            paginated_trips = paginator.page(page)
                        except PageNotAnInteger:
                            paginated_trips = paginator.page(1)
                        except EmptyPage:
                            paginated_trips = paginator.page(paginator.num_pages)
                        context['trips'] = paginated_trips
                        # Prepare trip data with distance and cost for only paginated trips
                        trip_data = []
                        for trip in paginated_trips:
                            distance = None
                            cost = None
                            if trip.start_odometer is not None and trip.end_odometer is not None:
                                distance = trip.end_odometer - trip.start_odometer
                                if vehicle.rate_per_km:
                                    cost = distance * float(vehicle.rate_per_km)
                            trip_data.append({
                                'trip': trip,
                                'distance': distance,
                                'cost': cost
                            })
                        context['trip_data'] = trip_data
                        context['paginator'] = paginator
                    except Vehicle.DoesNotExist:
                        pass
            except Firm.DoesNotExist:
                pass
        return context
