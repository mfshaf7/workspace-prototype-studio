import { DeliveryOperationFocus } from "@/components/delivery";

import styles from "./delivery-route.module.css";

export default function DeliveryRoutePage() {
  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <DeliveryOperationFocus />
      </div>
    </main>
  );
}
