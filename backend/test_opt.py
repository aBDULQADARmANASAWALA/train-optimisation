import asyncio
from app.config import get_settings
from app.repositories import TrainRepository, SectionRepository
from app.services import RailwayStateEngine, OptimizationService, PredictionService, SimulationOrchestrator
from app.main import SessionLocal, _parse_database_url
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

logging.basicConfig(level=logging.DEBUG)

def test():
    settings = get_settings()
    db_url = settings.database_url or _parse_database_url(settings.supabase_url)
    engine = create_engine(db_url)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    
    train_repo = TrainRepository(session)
    section_repo = SectionRepository(session)
    
    from datetime import datetime
    state_engine = RailwayStateEngine(train_repo, section_repo, datetime.utcnow())
    optimizer = OptimizationService(max_solver_time_seconds=10.0)
    predictor = PredictionService(train_repo, section_repo)
    
    orchestrator = SimulationOrchestrator(
        train_repo,
        section_repo,
        state_engine,
        optimizer,
        predictor,
        horizon_minutes=settings.optimization_horizon_minutes,
        rolling_step_minutes=settings.rolling_step_minutes,
    )
    
    # Needs to be attached to session for some persist calls? 
    # Actually wait SimulationOrchestrator needs db session
    orchestrator._db_session = session 
    
    res = orchestrator.execute_cycle()
    print("STATUS:", res.status)
    if res.optimization_result:
        print("INFEASIBLE REASONS:", getattr(res.optimization_result, "infeasibility_reasons", []))

if __name__ == "__main__":
    test()
