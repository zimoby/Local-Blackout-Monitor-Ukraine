from config import STATE_COLORS, STATE_NAMES, CHECK_DTEK
from colorama import Fore, Back, Style

def get_expected_state(schedule, current_time):
    day = current_time.weekday()
    hour = current_time.hour
    try:
        return schedule[day][hour]
    except KeyError:
        print(f"No schedule data available for day {day}, hour {hour}.")
        return -1

def compare_states(expected, actual, today_state):
    if today_state == -1 or expected == -1 or actual == -1:
        return "Немає доступних даних"
    
    if not today_state:
        if actual == 0:
            return "Співпадіння"
        
    if expected == actual:
        return "Співпадіння"
    
    return "Можливе неспівпадіння" if expected == 1 else "Неспівпадіння"


def calculate_ups_energy_usage(schedule, actual_states, hourly_consumption, ups_info):
    outage_consumption = {}
    for ups in ups_info:
        ups_id = f"UPS_{ups_info.index(ups)}"
        outage_consumption[ups_id] = {
            'total_kwh': 0,
            'hours': 0,
            'battery_ah': ups['battery_Ah']
        }
    
    current_outage = False
    for hour in range(24):
        if schedule[hour] == 2 and actual_states.get(hour, 0) == 2:
            current_outage = True
        elif current_outage:
            break
        
        if current_outage:
            for ups_id in outage_consumption:
                if hour in hourly_consumption and ups_id in hourly_consumption[hour]:
                    outage_consumption[ups_id]['total_kwh'] += hourly_consumption[hour][ups_id] / 1000
                    outage_consumption[ups_id]['hours'] += 1
    
    return outage_consumption

def display_today_schedule(schedule, current_time, current_actual_state, time_in_range_func, hourly_consumption, actual_states, ups_info):
    print("\nРозклад електропостачання на сьогодні:")
    for hour, state in enumerate(schedule):
        time_style = f"{Back.WHITE}{Fore.BLACK}" if hour == current_time.hour else ""

        limit_indicator = "[+]"
        state_color = STATE_COLORS[state]
        if CHECK_DTEK:
            limit_indicator = "[+]" if time_in_range_func(hour) else "[-]"
            state_color = STATE_COLORS[state] if time_in_range_func(hour) else STATE_COLORS[-1]

        current_hour = f"({STATE_COLORS[current_actual_state]}{STATE_NAMES[current_actual_state]}{Style.RESET_ALL})" if hour == current_time.hour else ""
        
        # Add energy consumption information
        consumption_info = ""
        if hour in hourly_consumption:
            for ups_id, consumption in hourly_consumption[hour].items():
                # Change color to red if electricity was actually off
                ups_color = Fore.RED if actual_states.get(hour, 0) == 2 else Fore.CYAN
                consumption_info += f" | {ups_color}{ups_id}: {consumption/1000:.2f} kWh{Style.RESET_ALL}"
        
        print(f"{time_style}{hour:02d}:00 {limit_indicator} {state_color}{STATE_NAMES[state]}{Style.RESET_ALL} {current_hour}{consumption_info}")

    # Calculate and display UPS energy usage during outages
    outage_consumption = calculate_ups_energy_usage(schedule, actual_states, hourly_consumption, ups_info)
    print("\nВикористання енергії ДБЖ під час відключень електроенергії:")
    for ups_id, data in outage_consumption.items():
        if data['hours'] > 0:
            battery_percentage = (data['total_kwh'] * 1000) / (data['battery_ah'] * 12) * 100  # Assuming 12V battery
            print(f"{ups_id}: {data['total_kwh']:.2f} kWh за {data['hours']} годин (приблизно {battery_percentage:.1f}% ємності акумулятора)")