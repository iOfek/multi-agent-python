from datetime import datetime
import os
from grpc import RpcContext
import yaml

def load_prompt(prompt_file: str) -> str:
    """Load a prompt from a YAML file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, "..", "prompts", prompt_file)
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_data = yaml.safe_load(f)
            return prompt_data.get('instructions', '')
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error loading prompt file {prompt_file}: {e}")
        return "" 
    
async def write_all_user_data(
    context: RpcContext,
) -> str:
    """כותב את כל המידע שנאסף על הלקוח לקובץ."""
    try:
        with open("user_data.txt", "w", encoding="utf-8") as f:
            f.write("=== נתוני לקוח מלאים ===\n\n")
            
            # מידע בסיסי
            f.write("מידע בסיסי:\n")
            f.write(f"שם: {context.userdata.name or 'לא צוין'}\n")
            f.write(f"גיל: {context.userdata.age or 'לא צוין'}\n")
            f.write(f"סטודנט: {'כן' if context.userdata.is_student else 'לא'}\n")
            if context.userdata.student_details:
                f.write(f"פרטי סטודנט: {context.userdata.student_details}\n")
            f.write("\n")
            
            # מידע על תעסוקה
            f.write("מידע על תעסוקה:\n")
            f.write(f"מועסק: {'כן' if context.userdata.is_employed else 'לא'}\n")
            f.write(f"משך עבודה: {context.userdata.employment_duration or 'לא צוין'}\n")
            f.write(f"הכנסה חודשית: {context.userdata.monthly_income or 'לא צוין'} ₪\n")
            f.write("\n")
            
            # מידע רפואי
            f.write("מידע רפואי:\n")
            f.write(f"מצב רפואי: {context.userdata.medical_condition or 'לא צוין'}\n")
            f.write(f"תאריך אבחון: {context.userdata.diagnosis_date or 'לא צוין'}\n")
            f.write(f"תרופות: {', '.join(context.userdata.medications) if context.userdata.medications else 'לא צוין'}\n")
            f.write(f"משך טיפול: {context.userdata.treatment_duration or 'לא צוין'}\n")
            f.write("\n")
            
            # דגלי זכאות
            f.write("סטטוס זכאות:\n")
            f.write(f"עומד בסף הכנסה: {'כן' if context.userdata.meets_income_threshold else 'לא'}\n")
            f.write(f"עבודה רציפה: {'כן' if context.userdata.has_continuous_employment else 'לא'}\n")
            f.write(f"תיעוד רפואי: {'כן' if context.userdata.has_medical_documents else 'לא'}\n")
            f.write("\n")
            
            # מידע נוסף
            if hasattr(context.userdata, 'medication_duration'):
                f.write(f"משך שימוש בתרופות: {context.userdata.medication_duration}\n")
            if hasattr(context.userdata, 'medication_changes'):
                f.write(f"שינויים בתרופות: {context.userdata.medication_changes}\n")
            if hasattr(context.userdata, 'side_effects'):
                f.write(f"תופעות לוואי: {context.userdata.side_effects}\n")
            if hasattr(context.userdata, 'medical_diagnosis'):
                f.write(f"אבחנה רפואית: {context.userdata.medical_diagnosis}\n")
            if hasattr(context.userdata, 'medication_type'):
                f.write(f"סוגי תרופות: {context.userdata.medication_type}\n")
            
            f.write(f"\nתאריך בדיקה: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
        
        return "✅ המידע המלא נשמר בהצלחה לקובץ user_data.txt"
    except Exception as e:
        logger = logging.getLogger("eligibility-check")
        logger.error(f"Error writing user data: {str(e)}")
        return "❌ אירעה שגיאה בשמירת המידע"