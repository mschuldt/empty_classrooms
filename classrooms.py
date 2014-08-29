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

d = "/home/michael/Dropbox/fall_2014/"
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

def extract_all():
    global buildings, classes
    global day_time_re_errors, room_building_errors, sub_class_extraction_errors
    global name_time_or_loc_errors, unreasonably_long_classes, extraction_errors
    global negative_times
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
                sub_class_extraction_errors.append([f, name, time, loc])
                continue
            #print("before add_class, buildings = " + str(buildings))
            for time, loc in zip(times, locations):
                add_class(Class(cname, name, time, loc, f))
            #print("after add_class, buildings = " + str(buildings))
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
