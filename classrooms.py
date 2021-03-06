#wget --wait=1 --random-wait --convert-links -r --level=2 -e robots=off -U mozilla https://schedulebuilder.berkeley.edu/explore/FL/2014/

import bs4
import subprocess
import re
import datetime
from operator import add

titles = []
single_names = ["HEARSTGYMCTS","BECHTEL AUD", "WHEELER AUD"]

def extract(filename):
    soup = bs4.BeautifulSoup(open(filename, "r").read())
    tables = soup.find_all("table")
    title = "-".join(soup.find("title").text.split('-')[:-2]).strip()
    titles.append((title.lower(), filename))
    section_table = None
    for t in tables:
        if t.get('id') == 'sections_table':
            section_table = t
    if not section_table:
        return False

    data = []
    for c in section_table.find_all("tr")[1:]:
        td = c.find_all("td")
        locations = [x.strip() for x in str(td[3].text).strip().split('\n')]
        locations = filter(lambda x: x, locations)
        times = [x.strip() for x in str(td[2].text).strip().split('\n')]
        times = filter(lambda x: x, times)
        data.append((td[0].text.strip(), times, locations));
    return title, data

#d = "/home/michael/Dropbox/fall_2014/"
d = "/home/michael/Desktop/schedulebuilder.berkeley.edu/explore/courses/FL/2014/"

p = subprocess.Popen("ls " + d, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
files = map(lambda x: x.strip(), p.stdout.readlines())

classes = []
day_time_re = "([UMWTRFS]+)[ ]+([0-9]{1,2}):?([0-9]{1,2})?([AP])?-([0-9]{1,2}):?([0-9]{1,2})?([AP])?"

extraction_errors = []
day_time_re_errors = []
room_building_errors = []
name_time_or_loc_errors = []
unreasonably_long_classes = []
sub_class_extraction_errors = []
negative_times = []

buildings = {} #maps building names to classrooms
classes = []

def to_mil_time(hour, minute, PM_p):
    hour = int(hour) + 12 if PM_p else int(hour)
    minute = int(minute) if minute else 1
    hour -= 1 #hours range: 0..23
    minute -= 1#minouts range: 0..59
    return hour, minute

n = 1
def add_class(c):
    global n, classes, buildings
    #print("n = " + str(n))
    n += 1
    classes.append(c)
    if not c.ok:
        return
    #print("buildings = " + str(buildings))
    #print("c.building = " + c.building)
    b = c.building
    building = buildings.get(b)
    if not building:
        building = Building(b)
        buildings[b] = building
    building.add_class(c)

    # classrooms = buildings.get(c.building)
    # #print("classrooms = " + str(classrooms))
    # if not classrooms:
    #     #print("not classrooms")
    #     #buildings[c.building] = {c.classroom : [c]}
    #     c = Classroom(c.building, c.classroom)
    #     c.add_class(c)
    #     buildings[c.building] = c
    # else:
    #     #print("yes classrooms")
    #     c = classrooms.get(c.classroom)
    #     #print("class_list = " + str(class_list))
    #     if not class_list:
    #         #print("not class_list")
    #         classrooms[c.classroom] = [c]
    #     else:
    #         #print("appending to class list")
    #         class_list.append(c)

class Class:
    def __init__(self, cname, name, time, loc, f):
        self.ok = False
        self.class_name = str(cname)
        self.name = str(name)
        self.text_time = str(time)
        self.text_loc = str(loc)
        self.file = f
        #parse time
        day_time = re.search(day_time_re, time)
        if not day_time:
            day_time_re_errors.append([f, cname, name, time])
            return
        self.days, s_h, s_m, s_AP, e_h, e_m, e_AP = day_time.groups()
        if s_AP and e_AP:
            AP_errors.append([f, cname, name, time])
            AP = s_AP
            #TODO
        s_PM = e_PM = None
        if e_AP == "P":
            if int(s_h or 0) + int(s_m or 0)/60.0 > int(e_h or 0) + int(e_m or 0)/60.0:
                s_PM = False
                e_PM = True
            else:
                s_PM = e_PM = True

        #AP_p = True if e_AP == "P" else False

        s_h, s_m = to_mil_time(s_h, s_m, s_PM)
        e_h, e_m = to_mil_time(e_h, e_m, e_PM)
        s = datetime.time(hour=s_h, minute=s_m, second=0, microsecond=0)
        e = datetime.time(hour=e_h, minute=e_m, second=0, microsecond=0)
        self.start_time = s
        self.end_time = e
        self.length = e_h + e_m/60.0 - s_h - s_m/60.0
        if self.length > 6:
            unreasonably_long_classes.append(self)
        if self.length < 0:
            negative_times.append(self)
        #parse location

        if (loc in single_names): loc = "<self> " + loc
        room_building = loc.split()
        if len(room_building) < 2:
            room_building_errors.append([f, cname, name, loc])
            return
        else:
            self.classroom = self.room = str(room_building[0])
            self.building = str(" ".join(room_building[1:]))
        self.ok = True

    def __repr__(self):
        return "<{}: {}>".format(self.name, self.text_time)

class Classroom:
    def __init__(self, building, number):
        self.number = self.name = number
        self.building = building
        self.classes = []
        self.n_classes = 0
    def __repr__(self):
        return "<room: {}>".format(self.number)
    def add_class(self, c):
        self.classes.append(c)
        self.n_classes += 1
    def __getitem__(self, key):
        if key >= 0 and n < self.n_classes:
            return self.classes[key]
        return False
    def building(self):
        return self.building

repeated_rooms = []

class Building:
    def __init__(self, name):
        self.name = name
        self.rooms = {}
        self.n_rooms = 0
    # def add_room(self, room):
    #     global repeated_rooms
    #     n = room.number
    #     x = self.rooms.get(n)
    #     if x:
    #         repeated_rooms.append(room)
    #     self.rooms[n] = room
    #     self.n_rooms += 1
    def __repr__(self):
        return "<{0}: {1} rooms>".format(self.name, self.n_rooms)
    def __getitem__(self, room):
        return self.rooms.get(room.number)
    def add_class(self, c):
        name = c.classroom
        r = self.rooms.get(name)
        if not r:
            r = Classroom(self.name, name)
            self.rooms[name] = r
            self.n_rooms += 1
        r.add_class(c)

data_loaded = False
def extract_all():
    global buildings, classes
    global day_time_re_errors, room_building_errors, sub_class_extraction_errors
    global name_time_or_loc_errors, unreasonably_long_classes, extraction_errors
    global negative_times, data_loaded
    day_time_re_errors = []
    room_building_errors = []
    name_time_or_loc_errors = []
    unreasonably_long_classes = []
    extraction_errors = []
    sub_class_extraction_errors = []
    negative_times = []
    buildings = {} #maps building names to classrooms
    classes = []
    for f in files:
        data = extract(d+f)
        if not data:
            extraction_errors.append(f)
            continue
        cname = data[0]
        for name, times, locations in data[1]:
            if not (name and times and times[0] and locations and locations[0]):
                sub_class_extraction_errors.append([f, name, times, locations])
                continue
            #print("before add_class, buildings = " + str(buildings))
            for time, loc in zip(times, locations):
                add_class(Class(cname, name, time, loc, f))
            #print("after add_class, buildings = " + str(buildings))
    data_loaded = True
    report()

def count_classrooms():
    return reduce(add, [len(buildings[x].rooms.keys()) for x in buildings])

def report():
    print("classes: " + str(len(classes)))
    print("buildings: " + str(len(buildings.keys())))
    print("classrooms: " + str(count_classrooms()))

def errors():
    print("extraction_errors: {}".format(len(extraction_errors)))
    print("day_time_re_errors: {}".format(len(day_time_re_errors)))
    print("room_building_errors: {}".format(len(room_building_errors)))
    print("name_time_or_loc_errors: {}".format(len(name_time_or_loc_errors)))
    print("sub_class_extraction_errors: {}".format(len(sub_class_extraction_errors)))
    print("repeated_rooms: {}".format(len(repeated_rooms)))
    print("unreasonably_long_classes: {}".format(len(unreasonably_long_classes)))
    print("negative_times: {}".format(len(negative_times)))

def building_names():
    return buildings.keys()

def building(name):
    return buildings[name.upper()]

def valid_building(building_name):
    return building_name.upper() in buildings

def rooms_in_building(building_name):
    name = building_name.upper()
    return valid_building(name) and buildings[name].rooms.values()

def classes_in_building(building_name, day = None):
    classes = []
    day = day.upper() if day else None
    for r in rooms_in_building(building_name):
        classes.extend([c for c in r.classes if day in c.days]
                       if day else r.classes)
    return classes

def class_names_in(building_name):
    x = set()
    for c in classes_in_building(building_name):
        x.add(c.class_name)
    for c in x:
        print c

def all_class_names():
    x = set()
    for c in classes: x.add(c.class_name)
    return list(x)

def sorted_classrooms(day, building_name = None):
    day = day.lower()
    class_times = {}
    if building_name:
        cls = classes_in_building(building_name)
    else:
        cls = classes
    for c in cls:
        if day in c.days:
            n = class_times.get(c.room, 0)
            class_times[c.room] = n + c.length
    x = list(class_times.iteritems())
    x.sort(key = lambda x: x[1])
    return x

def classes_in_room(building, room, day = None):
    ret = []
    for c in classes_in_building(building, day):
        if (c.room == room):
            ret.append(c)
    return ret

def find_class(classname):
    classname = classname.lower()
    results = []
    for c in classes:
        if classname in c.class_name.lower():
            results.append(c)
    if len(results) == 1:
        return results[0]
    return results

def find_filename(class_name):
    class_name = class_name.lower()
    ret = []
    for t in titles:
        if class_name in t[0]:
            ret.append(t)
    return ret

building = room = day = time = None

def print_class_list(classes):
    classes.sort(key = lambda x: x.start_time.hour + x.start_time.minute/60.0)
    for c in classes:
        print "{}, {}, {}".format(c.text_time, c.name, c.class_name)

def interactive():
    global building,room,day,time
    if not data_loaded:
        print("wait. extracting data first...")
        extract_all()
    pp = True
    def require_building():
        if not building:
            print ("Problem: you are not in a building")
            return False
        return True
    def require_room():
        if not room:
            print ("Problem: you are not in a room.")
            return False
        return True
    def require_day():
        if not day:
            print ("problem: I don't know what day it is")
            return False
        return True
    def require_time():
        if not time:
            print ("problem: I don't know what time it is")
            return False
        return True
    def print_location():
        print("\nlocation: {} {}".format(room or "", building))
        if time or day:
            print("time:     {} {}".format(day or "", time or ""))

    while True:
        print_location()
        e = False
        command = raw_input("==> ")
        cmd = command.lower().split()
        args = cmd[1:]
        cmd = cmd[0]
        n = len(args)
        if n == 0:
            if cmd == "exit" or cmd == "q":
                return
            elif cmd == "buildings":
                print(building_names())
                continue

            elif cmd == "rooms": #print rooms in 'building'
                if not require_building(): continue
                rooms = rooms_in_building(building)
                for r in rooms:
                    print r
                print ("found {} rooms.".format(len(rooms)))
                continue
            elif cmd == "classes": # list classes in current building or room
                if not building:
                    #list classes in every building
                    buildings =  building_names()
                    for b in buildings:
                        print ("Classes in building '{}':".format(b))
                        print_class_list(classes_in_building(b, day))
                    continue
                if not require_building(): continue
                if not room:
                    #print all classes in building
                    print_class_list(classes_in_building(building, day))
                    continue
                if not require_room(): continue
                #print all classes in room
                print_class_list(classes_in_room(building, room, day))
                continue
            elif cmd == "sorted":
                #print list of classrooms sorted by utilization
                if not require_day(): continue
                for c in sorted_classrooms(day, building):
                    print c
                continue
            elif cmd  == "..":
                #leave the current room or building
                if room:
                    print ("left room: {}".format(room))
                    room = None
                elif building:
                    print ("left building: {}".format(building))
                    building = None
                continue
        if n == 1:
            if cmd == "enter": #enter a building or classroom
                place = args[0]
                if building:
                    options = map(lambda x: x.name, rooms_in_building(building))
                    if place in options:
                        room = place
                    else:
                        print ("'{}' is not a room, you may enter:\n {}"
                               .format(place, ", ".join(options)))
                else:
                    options = building_names()
                    if place in map(lambda x: x.lower(), options):
                        building = place
                    else:
                        print ("'{}' is not a building, you may enter:\n {}"
                               .format(place, ", ".join(options)))
                continue
            if cmd == "day": #change the current day
                d = args[0]
                if d == "any":
                    day = None
                    continue
                if d == "th" or d == "thursday":
                    d = "r"
                elif len(d) > 3:
                    d = d[0]
                if d not in "mtwrfs":
                    print ("Problem: I don't know what day '{}' is.".format(d))
                    continue
                day = d
                continue
            if cmd == "time": #change current time
                #TODO: check that arg[0] is numeric
                h = int(arg[0]) - 1
                if h < 0 or h > 23:
                    print ("Problem: hour '{%d}' does not look valid (mil time).")
                    continue
                time = datetime.time(hour=h)
                continue
        if n == 2:
            if cmd == "time": #change current time
                #TODO: check that arg[0] is numeric
                h = int(arg[0]) - 1
                m = int(arg[1]) - 1
                if h < 0 or h > 23:
                    print ("Problem: hour '{%d}' does not look valid (mil time).")
                    e = True
                if m < 0 or m > 59:
                    print ("Problem: minute '{%d}' does not look valid (mil time).")
                    e = True
                if e: continue
                time = datetime.time(hour=h, minute=m)

        print("exec({}) =".format(command))
        exec command in globals()

i = interactive

# sort_rooms:
#      if room and day: list of classrooms sorted by utilization (assending order)

# find_best_rooms:
#      if building and day: list the rooms most available for the current day and time.




