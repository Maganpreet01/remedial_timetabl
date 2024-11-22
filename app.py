import os
import re
from flask import Flask, render_template, request, send_file
import PyPDF2
from fpdf import FPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'


def extract_pdf_text(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page_num in range(len(reader.pages)):
            text += reader.pages[page_num].extract_text()
    return text


def extract_free_slots(text):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    timeslots = ['09:00-10:00 AM', '10:00-11:00 AM', '11:00-12:00 PM', '12:00-01:00 PM',
                 '01:00-02:00 PM', '02:00-03:00 PM', '03:00-04:00 PM', '04:00-05:00 PM', '05:00-06:00 PM']

    free_slots = {day: [] for day in days}

    for day in days:
        day_pattern = rf'{day}.*?(?=(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|$))'
        day_block = re.search(day_pattern, text, re.DOTALL)
        if day_block:
            occupied_times = re.findall(r'\d{2}:\d{2}-\d{2}:\d{2} [APM]{2}', day_block.group())
            for slot in timeslots:
                if slot not in occupied_times:
                    free_slots[day].append(slot)

    print("DEBUG: Extracted Free Slots:", free_slots)  
    return free_slots


def extract_faculty_list(text):
    """Extract faculty list with acronyms from the timetable text."""
    faculty_list = {}
    faculty_pattern = re.search(r'Faculty.*?((?:[A-Z]{2,3}\s+[A-Za-z. ]+\n?)+)', text, re.DOTALL)
    if faculty_pattern:
        faculty_text = faculty_pattern.group(1)
        faculties = re.findall(r'([A-Z]{2,3})\s+([A-Za-z. ]+)', faculty_text)
        for acronym, name in faculties:
            faculty_list[acronym.strip()] = name.strip()

    print("DEBUG: Extracted Faculty List:", faculty_list)  # Debug
    return faculty_list


def generate_remedial_timetable(free_slots, teacher_assignments, output_path):
    """Generate a remedial timetable PDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Remedial Timetable', ln=True, align='C')

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(50, 10, 'Day', border=1, align='C')
    pdf.cell(70, 10, 'Time Slot', border=1, align='C')
    pdf.cell(70, 10, 'Assigned Teacher', border=1, align='C')
    pdf.ln()

    pdf.set_font('Arial', '', 12)
    for day, slots in free_slots.items():
        for slot in slots:
            teacher = teacher_assignments.get((day, slot), 'Not Assigned')
            pdf.cell(50, 10, day, border=1)
            pdf.cell(70, 10, slot, border=1)
            pdf.cell(70, 10, teacher, border=1)
            pdf.ln()

    pdf.output(output_path)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'timetable' not in request.files:
            return 'No file uploaded', 400

        file = request.files['timetable']
        if file.filename == '':
            return 'No file selected', 400

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        timetable_text = extract_pdf_text(filepath)
        print("DEBUG: Full Extracted Text:", timetable_text[:500])  # Debug

        free_slots = extract_free_slots(timetable_text)
        faculty_list = extract_faculty_list(timetable_text)

        # Verify extracted data
        print("DEBUG: Free Slots Per Day:", free_slots)
        print("DEBUG: Faculty List Extracted:", faculty_list)

        teacher_assignments = {}
        available_teachers = list(faculty_list.values())
        print("DEBUG: Teachers Available Initially:", available_teachers)

        # Round-robin assignment
        for day, slots in free_slots.items():
            for slot in slots:
                if available_teachers:
                    teacher = available_teachers.pop(0)  # Take first teacher
                    print(f"DEBUG: Assigning {teacher} to {day} {slot}")
                    teacher_assignments[(day, slot)] = teacher
                    available_teachers.append(teacher)  # Rotate teacher to the end
                else:
                    teacher_assignments[(day, slot)] = 'Not Assigned'

        print("DEBUG: Final Teacher Assignments:", teacher_assignments)

        remedial_timetable_path = os.path.join(app.config['UPLOAD_FOLDER'], 'remedial_timetable.pdf')
        generate_remedial_timetable(free_slots, teacher_assignments, remedial_timetable_path)

        return send_file(remedial_timetable_path, as_attachment=True)

    return render_template('index.html')


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
