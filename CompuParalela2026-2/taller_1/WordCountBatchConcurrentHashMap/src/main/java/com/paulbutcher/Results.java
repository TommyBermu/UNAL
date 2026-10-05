package com.paulbutcher;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * Utilidad para imprimir las palabras mas y menos repetidas
 * (punto 10 del taller).
 */
class Results {

  public static void printTopAndBottom(Map<String, Integer> counts, int n) {
    System.out.println("Total de palabras distintas: " + counts.size());

    List<Map.Entry<String, Integer>> entries =
        new ArrayList<Map.Entry<String, Integer>>(counts.entrySet());
    entries.sort(Comparator.comparingInt(Map.Entry<String, Integer>::getValue).reversed());

    int size = entries.size();
    int limit = Math.min(n, size);

    System.out.println("\n== " + limit + " palabras con MAS repeticiones ==");
    for (int i = 0; i < limit; ++i) {
      Map.Entry<String, Integer> e = entries.get(i);
      System.out.println((i + 1) + ". " + e.getKey() + " -> " + e.getValue());
    }

    System.out.println("\n== " + limit + " palabras con MENOS repeticiones ==");
    for (int i = 0; i < limit; ++i) {
      Map.Entry<String, Integer> e = entries.get(size - 1 - i);
      System.out.println((i + 1) + ". " + e.getKey() + " -> " + e.getValue());
    }
  }
}
