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


def display_today_schedule(schedule, current_time, current_actual_state, time_in_range_func, hourly_consumption):
    day = current_time.weekday()
    next_day = (day + 1) % 7
    today_schedule = schedule.get(day, [])
    next_day_schedule = schedule.get(next_day, [])

    print("\nРозклад електропостачання на сьогодні:")
    for hour, state in enumerate(today_schedule):
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
                consumption_info += f" | UPS_{ups_id}: {consumption/1000:.2f} kWh"
        
        print(f"{time_style}{hour:02d}:00 {limit_indicator} {state_color}{STATE_NAMES[state]}{Style.RESET_ALL} {current_hour}{consumption_info}")

    print("\nПерші 5 годин наступного дня:")
    for hour, state in enumerate(next_day_schedule[:5]):
        print(f"{hour:02d}:00 {STATE_COLORS[state]}{STATE_NAMES[state]}{Style.RESET_ALL}")