import type { Metadata } from "next";
import MyReservations from "./MyReservations";

export const metadata: Metadata = { title: "나의 예약·대여" };

export default function MePage() {
  return <MyReservations />;
}
