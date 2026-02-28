# Backend Examples and Tests

This directory contains working examples and tests for each backend component.

## Files Overview

### 1. **testing_config.py** - Configuration Module
- **Purpose**: Demonstrates how to load and use configuration settings
- **Examples Included**:
  - Basic settings access
  - Logging setup
  - Singleton pattern verification
  - Validation demos
  - Environment variable overrides

**Run it:**
```bash
cd backend
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-key
python -m examples.testing_config
```

---

### 2. **testing_models.py** - Database Models
- **Purpose**: Shows how to create and work with ORM model instances
- **Examples Included**:
  - Creating stations
  - Creating sections between stations
  - Creating trains
  - Creating train schedules
  - Creating and updating train states
  - Creating optimization logs
  - Using TrainStatus and SignallingType enums

**Run it:**
```bash
cd backend
python -m examples.testing_models
```

**Key Takeaways**:
- Models are UUIDs-based for distributed systems
- Relationships are properly set up (bidirectional)
- Timestamps are automatic
- Enums provide type safety

---

### 3. **testing_repositories.py** - Data Access Layer
- **Purpose**: Demonstrates repository pattern for database operations
- **Examples Included**:
  - Setting up in-memory SQLite database
  - Getting active trains
  - Retrieving train schedules
  - Getting current train states
  - Updating single train state
  - Bulk updating multiple trains
  - Getting train by ID
  - Getting section information
  - Error handling patterns

**Run it:**
```bash
cd backend
python -m examples.testing_repositories
```

**Key Takeaways**:
- Repositories abstract database access
- All methods return dictionaries (not ORM objects)
- Error handling is comprehensive
- Transactions are automatic

---

### 4. **testing_state_engine.py** - Core State Management Engine ⭐
- **Purpose**: Demonstrates the RailwayStateEngine (critical service)
- **Examples Included**:
  - Setting up a test network (4 stations, 4 sections, 3 trains)
  - Initializing the state engine
  - Detecting conflicts:
    - Capacity violations
    - Headway violations
    - Platform conflicts
  - Checking section loads/utilization
  - Predicting future conflicts within horizon window
  - Snapshotting complete state
  - Rolling horizon time updates
  - Updating train states

**Run it:**
```bash
cd backend
python -m examples.testing_state_engine
```

**Key Capabilities Tested**:
- ✓ NetworkX graph building
- ✓ Real-time conflict detection
- ✓ Section utilization analysis
- ✓ Future conflict prediction
- ✓ State snapshots for logging/analysis
- ✓ Rolling horizon support
- ✓ Deterministic behavior

---

### 5. **testing_optimizer.py** ⭐⭐ - CP-SAT Constraint Programming Optimizer
- **Purpose**: Demonstrates the core optimization engine using Google OR-Tools
- **Examples Included**:
  - Creating optimization snapshots from current state
  - Running basic optimization with 5 trains
  - Examining adjusted schedules
  - Priority-weighted delay minimization
  - Rolling horizon optimization (multiple cycles)
  - Handling infeasible scenarios
  - Warm-start from previous solutions

**Run it:**
```bash
cd backend
python -m examples.testing_optimizer
```

**Key Capabilities**:
- ✓ Constraint programming with OR-Tools CP-SAT
- ✓ Decision variables for arrival/departure times
- ✓ Capacity, headway, and platform constraints
- ✓ Weighted delay minimization objective
- ✓ Handles 100+ trains efficiently
- ✓ Rolling horizon with warm starts
- ✓ Graceful infeasibility detection
- ✓ Solver time limits enforced
- ✓ No database access (pure computation)

---

### 6. **testing_predictor.py** 🤖 - Machine Learning Predictions
- **Purpose**: Demonstrates ML-based prediction service for delays and congestion
- **Examples Included**:
  - Training delay prediction models
  - Training congestion prediction models
  - Making delay predictions with confidence intervals
  - Making congestion predictions with recommendations
  - Batch predictions for multiple trains/sections
  - Error tracking and statistics
  - Data drift detection
  - Automatic retraining on drift
  - Feature importance analysis
  - Model metadata retrieval

**Run it:**
```bash
cd backend
python -m examples.testing_predictor
```

**Key Capabilities**:
- ✓ RandomForest models with scikit-learn
- ✓ Feature engineering (time, load, priority)
- ✓ Confidence scoring and prediction intervals
- ✓ 90% confidence intervals on predictions
- ✓ Drift detection with automatic retraining
- ✓ Extensible architecture (ready for deep learning)
- ✓ Model persistence (pickle)
- ✓ Feature importance tracking

---

## How to Use These Examples

### For Learning
1. Start with `testing_models.py` to understand data structures
2. Move to `testing_config.py` to see configuration setup
3. Check `testing_repositories.py` to learn about data access
4. Study `testing_state_engine.py` to understand the core engine
5. Learn `testing_optimizer.py` for optimization strategies
6. Advanced: Explore `testing_predictor.py` for ML predictions

### For Testing During Development
1. Run examples to verify changes don't break basic functionality
2. Use examples as templates for writing unit tests
3. Add more test cases as new features are developed

### For Integration Testing
1. Use `testing_state_engine.py` as a template for end-to-end tests
2. Create more complex network scenarios
3. Test edge cases (empty networks, single train, capacity overload, etc.)

### For Documentation
- These files serve as reference implementation
- Show best practices for using each component
- Provide executable examples (not just docstrings)

---

## Database Setup for Testing

### In-Memory (Fast, No Persistence)
```python
from sqlalchemy import create_engine
from app.models import Base

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
```

### PostgreSQL (Production-like)
```python
from sqlalchemy import create_engine
from app.config import settings

engine = create_engine(
    f"postgresql://user:password@localhost/mindicator",
    echo=False,
)
Base.metadata.create_all(engine)
```

---

## Important Notes

1. **Environment Variables**: Some examples require SUPABASE_URL and SUPABASE_KEY
2. **Database**: Examples use in-memory SQLite by default
3. **Deterministic**: All examples produce same output given same inputs
4. **No Side Effects**: Examples don't modify production databases

---

## Next Steps

After running these examples:

1. ✅ Models are working
2. ✅ Repositories provide data access
3. ✅ Configuration is loaded
4. ✅ State engine detects conflicts
5. ✅ Optimizer minimizes delays with CP-SAT
6. ✅ Predictor forecasts delays and congestion
7. Next: Build API endpoints (routes)
8. Next: Create simulator service
9. Next: Deploy and test

---

## Troubleshooting

### ImportError: No module named 'app'
**Solution**: Run from `backend/` directory
```bash
cd backend
python -m examples.testing_config
```

### ModuleNotFoundError: No module named 'sqlalchemy'
**Solution**: Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### ValidationError in testing_config.py
**Solution**: Set required environment variables
```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-key
```

---

## Adding New Examples

When you add a new component, create a corresponding example file:

1. **Naming**: `testing_<component_name>.py`
2. **Structure**:
   - Setup function (if needed)
   - Multiple example functions (one per feature)
   - Main block with try/except
   - Print success message

3. **Template**:
```python
"""
Examples and tests for <component>.

Demonstrates:
- Feature 1
- Feature 2
"""

def example_feature_1():
    print("=== Feature 1 ===")
    # ... example code ...

if __name__ == "__main__":
    try:
        example_feature_1()
        print("\n✅ All examples completed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
```

---

Happy testing! 🚀
