"""GoUsage 打包入口."""
import atexit

from app.main import main, shutdown

if __name__ == "__main__":
    atexit.register(shutdown)
    main()
