import pandas as pd
from session_management.models import Student

def load_excel_data(file_path='Data.xlsx'):
    """
    Load register_number, name, and phone_number from an Excel file into the Student model.
    Other fields (dob, gender, father_name, mother_name, email, aadhar_number, password, updated_at)
    are left as NULL.
    
    Args:
        file_path (str): Path to the Excel file (default: 'Data.xlsx')
    
    Returns:
        dict: Summary of successful and failed insertions
    """
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        success_count = 0
        errors = []

        # Insert each row into Student model
        for index, row in df.iterrows():
            try:
                # Validate required fields
                reg_no = str(row['Reg.No']).upper().strip()
                name = str(row.get('Name of the Student', '')).strip()
                phone_number = str(row.get('Student No', '')).strip()

                if not reg_no:
                    raise ValueError("Register number is missing")
                if not name:
                    raise ValueError("Name is missing")
                if not phone_number:
                    raise ValueError("Phone number is missing")

                # Format phone number with +91
                if not phone_number.startswith('+91'):
                    phone_number = '+91' + phone_number.lstrip('0')

                Student.objects.create(
                    register_number=reg_no,
                    name=name,
                    phone_number=phone_number
                )
                print(f"Inserted student: {reg_no}")
                success_count += 1
            except Exception as e:
                error_msg = f"Error inserting {row.get('Reg.No', 'unknown')}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)

        return {
            'status': 'success',
            'inserted': success_count,
            'errors': errors
        }
    except Exception as e:
        print(f"Failed to load Excel file: {str(e)}")
        return {
            'status': 'error',
            'inserted': 0,
            'errors': [f"Failed to load Excel file: {str(e)}"]
        }

if __name__ == '__main__':
    load_excel_data()