import { DeliveryOperationFocus } from "@/components/delivery";

import styles from "./delivery-route.module.css";

export default function DeliveryRoutePage() {
  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <p className={styles.kicker}>Governance Operations Console</p>
          <h1 className={styles.title}>Delivery Integration Route</h1>
          <p className={styles.description}>
            Clean route for the new Delivery architecture while the root console
            page is still being reconciled.
          </p>
        </header>
        <DeliveryOperationFocus />
      </div>
    </main>
  );
}
