import pandas as pd
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def generate_test_data():
    print("Generating sample volunteers.xlsx...")
    volunteers_data = {
        "ID": ["VOL-01", "VOL-02", "VOL-03", "VOL-04", "VOL-05"],
        "Name": ["Arun Kumar", "Bala Chandran", "Chitra Devi", "Deepak Raj", "Elango K"],
        "Address": [
            "Adyar, Chennai",
            "Guindy, Chennai",
            "T. Nagar, Chennai",
            "Velachery, Chennai",
            "Mylapore, Chennai"
        ],
        "Phone": ["9876543210", "9876543211", "9876543212", "9876543213", "9876543214"],
        "Skill": ["Math", "Science", "English", "Math", "Computers"]
    }
    df_vol = pd.DataFrame(volunteers_data)
    df_vol.to_excel(DATA_DIR / "volunteers.xlsx", index=False)
    print(f"Saved: {DATA_DIR / 'volunteers.xlsx'}")

    print("Generating sample students.xlsx...")
    students_data = {
        "ID": [f"STUD-{i:02d}" for i in range(1, 21)],
        "Name": [
            "Aakash S", "Bhavana R", "Charan M", "Divya V", "Eshwar P",
            "Farhan A", "Gowri N", "Hariharan T", "Indhu J", "Jaya Kumar",
            "Karthik S", "Lavanya G", "Manoj K", "Nisha R", "Oviya M",
            "Pradeep K", "Ramya S", "Suresh P", "Tharun A", "Vidya L"
        ],
        "Address": [
            "Besant Nagar, Chennai",
            "Thiruvanmiyur, Chennai",
            "Nungambakkam, Chennai",
            "Kodambakkam, Chennai",
            "Saidapet, Chennai",
            "Pallavaram, Chennai",
            "Chromepet, Chennai",
            "Tambaram East, Chennai",
            "Anna Nagar, Chennai",
            "Mogappair, Chennai",
            "Egmore, Chennai",
            "Royapettah, Chennai",
            "Triplicane, Chennai",
            "Kotturpuram, Chennai",
            "Sholinganallur, Chennai",
            "Perungudi, Chennai",
            "Thoraipakkam, Chennai",
            "Madipakkam, Chennai",
            "Medavakkam, Chennai",
            "Tambaram Sanatorium, Chennai"
        ],
        "Phone": [f"91234567{i:02d}" for i in range(1, 21)],
        "Grade": ["Class 8", "Class 9", "Class 10", "Class 8", "Class 9", 
                  "Class 10", "Class 8", "Class 9", "Class 10", "Class 8",
                  "Class 9", "Class 10", "Class 8", "Class 9", "Class 10",
                  "Class 8", "Class 9", "Class 10", "Class 8", "Class 9"]
    }
    df_stud = pd.DataFrame(students_data)
    df_stud.to_excel(DATA_DIR / "students.xlsx", index=False)
    print(f"Saved: {DATA_DIR / 'students.xlsx'}")

if __name__ == "__main__":
    generate_test_data()
