import json
from datetime import datetime, date
from database.models import *
from database.db_manager import db_manager

class DataBackupManager:
    def row_to_dict(self, row):
        d = {}
        for column in row.__table__.columns:
            val = getattr(row, column.name)
            if isinstance(val, (datetime, date)):
                d[column.name] = val.isoformat()
            else:
                d[column.name] = val
        return d

    def serialize_formulation(self, formulation_id):
        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).get(formulation_id)
            if not formulation:
                return None
            
            data = {
                "table": "formulations",
                "data": self.row_to_dict(formulation),
                "items": [self.row_to_dict(item) for item in formulation.items]
            }
            return json.dumps(data, default=str)
        finally:
            session.close()

    def serialize_production_formulation(self, pf_id):
        session = db_manager.get_session()
        try:
            pf = session.query(ProductionFormulation).get(pf_id)
            if not pf:
                return None
            
            data = {
                "table": "production_formulations",
                "data": self.row_to_dict(pf),
                "steps": [self.row_to_dict(step) for step in pf.steps]
            }
            return json.dumps(data, default=str)
        finally:
            session.close()

    def serialize_production_run(self, run_id):
        session = db_manager.get_session()
        try:
            run = session.query(ProductionRun).get(run_id)
            if not run:
                return None
            
            data = {
                "table": "production_runs",
                "data": self.row_to_dict(run)
            }
            return json.dumps(data, default=str)
        finally:
            session.close()

    def restore_data(self, json_data):
        try:
            data = json.loads(json_data)
            table = data.get("table")
        except:
            return False, "Invalid JSON format"
        
        session = db_manager.get_session()
        try:
            if table == "formulations":
                f_data = data["data"]
                # Convert date strings back to objects if necessary (SQLAlchemy might handle it but better to be safe)
                # For SQLite/SQLAlchemy, strings for dates usually work if column type matches, 
                # but models define some as String(20) and some as Date.
                # Formulation uses String for dates mostly.
                
                # Check for existing
                existing = session.query(Formulation).get(f_data['id'])
                if existing:
                    # If exists, we delete it first to ensure clean restore (cascade delete items)
                    session.delete(existing)
                    session.flush()
                
                # Create main object
                formulation = Formulation(**f_data)
                
                # Add items
                if "items" in data:
                    for item_data in data["items"]:
                        # Remove foreign key if it interferes, but keeping it ensures mapping
                        item = FormulationItem(**item_data)
                        session.add(item) # Add item directly
                
                session.merge(formulation) # Merge formulation
                session.commit()
                
            elif table == "production_formulations":
                pf_data = data["data"]
                
                existing = session.query(ProductionFormulation).get(pf_data['id'])
                if existing:
                    session.delete(existing)
                    session.flush()
                    
                # Handle dates for ProductionFormulation (effective_date is Date)
                if pf_data.get('effective_date'):
                    try:
                        pf_data['effective_date'] = datetime.fromisoformat(pf_data['effective_date']).date()
                    except:
                        pass # Keep as string if fail
                
                pf = ProductionFormulation(**pf_data)
                
                if "steps" in data:
                    for step_data in data["steps"]:
                        step = ProductionStep(**step_data)
                        session.add(step)
                        
                session.merge(pf)
                session.commit()
                
            elif table == "production_runs":
                r_data = data["data"]
                
                existing = session.query(ProductionRun).get(r_data['id'])
                if existing:
                    session.delete(existing)
                    session.flush()
                
                # Handle Date fields
                for date_field in ['run_date', 'production_date']:
                    if r_data.get(date_field):
                        try:
                            r_data[date_field] = datetime.fromisoformat(r_data[date_field]).date()
                        except:
                            pass

                run = ProductionRun(**r_data)
                session.merge(run)
                session.commit()
            
            else:
                return False, f"Unknown table type: {table}"
                
            return True, "Success"
        except Exception as e:
            session.rollback()
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            session.close()

backup_manager = DataBackupManager()
